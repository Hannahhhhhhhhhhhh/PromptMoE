import copy
import pickle
import torch
import torch.nn as nn
import torch.nn.functional as F


class UniRouteMoELayer(nn.Module):
    def __init__(self, hidden_size, expert, num_experts, num_beams=2, layer_judge=None, route_method="pre-route", weight_type="ffn_prob"):
        # remove hash list
        nn.Module.__init__(self)
        self.num_experts = num_experts #(1+other)
        self.num_route_experts = num_experts-1
        self.num_beams = num_beams
        self.num_route_beam = num_beams-1

        self.experts = nn.ModuleList([copy.deepcopy(expert) for i in range(num_experts)])
        self.hidden_size = hidden_size
        self.layer_judge = layer_judge
        self.weight_type = weight_type

        self.route_method = route_method
        if self.route_method == "pre-route-uni":
            self.gate = nn.Linear(hidden_size, num_experts, bias=False).float()
        elif self.route_method in ["post-route-uni"]:
            gate = nn.Linear(hidden_size, 1, bias=False).float()
            self.gate = gate

    def _importance_auxiliary_loss(self, prob_gate):
        # From VMOE
        # _importance_auxiliary_loss
        axis = tuple(range(prob_gate.ndim - 1))  # All except last.
        importance_per_expert = torch.sum(prob_gate, dim=axis)
        std_importance_per_expert = torch.std(importance_per_expert)
        mean_importance_per_expert = torch.mean(importance_per_expert)
        # Compute coefficient of variation (i.e. std/mean) squared.
        return (std_importance_per_expert / mean_importance_per_expert)**2


    def beam_search(self, current_scores_log, beam_scores, expert_route, batch_size):
        if self.layer_judge=='first' and self.route_method in ['pre-route-uni', 'post-route-uni']:
            # current_scores_log torch.Size([bz, num_experts-1])
            assert beam_scores==None and expert_route==None
            current_scores = torch.exp(current_scores_log)
            topk_values, gate = torch.topk(current_scores, self.num_route_beam, dim=1) # gate, 每个样本被分配的expert: torch.Size([bz, topk])
            beam_scores = topk_values.view(self.num_route_beam * batch_size) # torch.Size([bz * num_beams])
            expert_route = gate.view(self.num_route_beam * batch_size).unsqueeze(1) # torch.Size([bz * num_beams,1])
            beam_idx = torch.tensor(range(self.num_route_beam * batch_size))
            
        else:
            batch_size = int(batch_size // self.num_route_beam)
            next_scores_raw = current_scores_log + torch.log(beam_scores).unsqueeze(1)  # torch.Size([4*3, 5]) # 取log 之后，可以直接相加概率
            next_scores_exp = torch.exp(next_scores_raw)

            next_scores_raw1 = next_scores_exp.view(
                batch_size, self.num_route_beam * self.num_route_experts
            )  # torch.Size([bz, num_route_beam*num_route_experts])

            next_scores, next_experts = torch.topk(next_scores_raw1, self.num_route_beam, dim=1, largest=True, sorted=True)
            # next_tokens torch.Size([bz, num_route_beam])

            next_batch_beam = list()
            for batch_idx in range(batch_size):
                next_sent_beam = list()
                for rank, (expert_id, expert_score) in enumerate(
                    zip(next_experts[batch_idx], next_scores[batch_idx])
                ):
                    expert_id = expert_id.item()
                    beam_id = expert_id // self.num_route_experts
                    ex_id = expert_id % self.num_route_experts
                    effective_beam_id = batch_idx*self.num_route_beam + beam_id

                    next_sent_beam.append((expert_score, ex_id, effective_beam_id))
                next_batch_beam.extend(next_sent_beam)

            beam_scores = beam_scores.new([x[0] for x in next_batch_beam])
            beam_experts = expert_route[:,-1].new([x[1] for x in next_batch_beam])
            beam_idx = expert_route[:,-1].new([x[2] for x in next_batch_beam])
            pre_route = expert_route[beam_idx,:]
            expert_route = torch.cat([pre_route, beam_experts.unsqueeze(1)], dim=-1)

        return beam_scores, expert_route, beam_idx


    def forward_gate(self, x):
        """
            TODO: Pre forward gate
            x : torch.Size([bz*(num_beams-1), 32, 768]) or torch.Size([bz, 32, 768]) 
            prob_gate : torch.Size([bz*(num_beams-1), num_experts])  or torch.Size([bz, num_experts]) 
        """
        attention_mask = torch.ones(x.shape[0], x.shape[1]).to(x.device)
        x_masked = x * attention_mask.unsqueeze(-1) # torch.Size([bz*(num_beams-1), 32, 768])
        x_average = torch.mean(x_masked, dim=1) # torch.Size([bz*(num_beams-1), 768])
        logits_gate = self.gate(x_average) # torch.Size([bz*(num_beams-1), num_experts])
        prob_gate = F.softmax(logits_gate, dim=-1) #  torch.Size([bz*(num_beams-1), num_experts])
        return prob_gate

    def forward_expert_ffn(self, x, expert_select, current_scores):
        """
            x_repeat : [bz*num_beams, 32,768]
            expert_select : [bz*num_beams]
            current_scores : [bz*num_beams, num_experts] / [bz, num_experts]
        """
        # import pdb;pdb.set_trace()
        outputs = list()
        for i  in range(self.num_experts-1):
            output_x = self.experts[i].forward(x)
            outputs.append(output_x.unsqueeze(1))
        candidate_output = torch.cat(outputs, dim=1) 
        expert_select_matrix = F.one_hot(expert_select, self.num_experts)
        if self.weight_type == 'ffn_prob':
            tmp_prob = current_scores * expert_select_matrix
            candidate_output = candidate_output * tmp_prob.unsqueeze(-1).unsqueeze(-1)
        else:
            candidate_output = candidate_output * expert_select_matrix.unsqueeze(-1).unsqueeze(-1)
        output = torch.sum(candidate_output, dim=1)
        # import pdb;pdb.set_trace()
        return output # torch.Size([bz*(num_beams-1), 32, 768])

    def forward_pre_route(self, x, beam_scores, expert_route, use_log=True):
        
        current_scores = self.forward_gate(x) # [bz, num_beams] / [bz*num_beams, num_beams]

        importance_loss = self._importance_auxiliary_loss(current_scores)

        if use_log:
            current_scores_log = torch.log(current_scores) # 取log之后可以直接相加
        else:
            current_scores_log = current_scores
        # import pdb;pdb.set_trace()
        batch_size, num_tokens = x.shape[0], x.shape[1]
        beam_scores, expert_route, beam_idx = self.beam_search(current_scores_log, beam_scores, expert_route, batch_size)
        current_expert_select = expert_route[:,-1]

        if self.layer_judge=='first': # expand first dim to batch_size * num_beams
            replicated_tensor = x.unsqueeze(1).expand(batch_size, self.num_beams, num_tokens, self.hidden_size)
            x = replicated_tensor.contiguous().view(-1, num_tokens, self.hidden_size) # [bz*num_beams, 32,768]
            current_scores_t = current_scores.unsqueeze(1).expand(batch_size, self.num_beams, self.num_experts)
            current_scores = current_scores_t.contiguous().view(-1, self.num_experts) # [bz*num_beams, num_experts]

        input_x = x[beam_idx]
        candidate_output = self.forward_expert_ffn(input_x, current_expert_select, current_scores) # [bz*num_beams, 32,768]
        # import pdb;pdb.set_trace()
        return candidate_output, beam_scores, expert_route, beam_idx, importance_loss

    def forward_post_route_uni(self, x, beam_scores, expert_route, use_log=True):
        
        if beam_scores == None:
            batch_size = x.shape[0]
            x_masked, x_uniexpert = x, x # torch.Size([bz, 32, 768])
        elif x.shape[0]/self.num_beams == beam_scores.shape[0]/self.num_route_beam:
            batch_size = int(x.shape[0]/self.num_beams)
            select_universal = [i*self.num_beams+self.num_route_beam for i in range(batch_size)]
            select_expert = [ x for x in range(batch_size*self.num_beams) if x not in select_universal]
            x_masked, x_uniexpert = x[select_expert],x[select_universal]
        num_tokens = x.shape[1]

        import pdb; pdb.set_trace()

        def forward_expert(input_x, expert_idx):
            output_x = self.experts[expert_idx].forward(input_x)
            return output_x
        
        ####################
        ### route expert
        ####################
        outputs = list()
        logits_gate_lst = list()
        for expert_idx in range(self.num_route_experts): # num_expert-1
            output_x = forward_expert(x_masked, expert_idx)
            output_x_aver = torch.mean(output_x, dim=1)
            gate_score = self.gate(output_x_aver)
            logits_gate_lst.append(gate_score)
            outputs.append(output_x.unsqueeze(0))

        candidate_output_raw = torch.cat(outputs) # torch.Size([num_expert-1, bz*(num_beam-1), 32, 768])
        logits_gate = torch.cat(logits_gate_lst,dim=1)# torch.Size([bz*(num_beam-1), num_expert-1])
        current_scores = F.softmax(logits_gate, dim=-1) # torch.Size([bz*(num_beam-1), num_expert-1])
        if use_log:
            current_scores_log = torch.log(current_scores) # 取log之后可以直接相加 torch.Size([bz*(num_beam-1), num_expert-1])
        else:
            current_scores_log = current_scores
        
        importance_loss = self._importance_auxiliary_loss(current_scores)
        beam_scores, expert_route, beam_idx = self.beam_search(current_scores_log, beam_scores, expert_route, current_scores_log.shape[0])
        # beam_scores torch.Size([bz*(num_beam-1)]), expert_route torch.Size([bz*(num_beam-1), layer_n])
        current_select_expert = expert_route[:,-1] # torch.Size([bz*(num_beam-1)])

        import pdb; pdb.set_trace()
        if self.layer_judge == 'first':
            replicated_tensor = candidate_output_raw.unsqueeze(2).expand(self.num_route_experts, batch_size, self.num_route_beam, num_tokens, self.hidden_size)
            candidate_output_raw = replicated_tensor.contiguous().view(self.num_route_experts, -1, num_tokens, self.hidden_size) # [bz*num_beams, 32,768]
            current_scores_t = current_scores.unsqueeze(1).expand(batch_size, self.num_route_beam, self.num_route_experts)
            current_scores = current_scores_t.contiguous().view(-1, self.num_route_experts) # [bz*(num_beams-1), num_experts-1]
        
        import pdb; pdb.set_trace()
        candidate_output = candidate_output_raw.permute(1, 0, 2, 3)[beam_idx] # torch.Size([8, 2, 32, 768])
        expert_select_matrix = F.one_hot(current_select_expert, self.num_route_experts)
        if self.weight_type == 'ffn_prob':
            tmp_prob = current_scores[beam_idx] * expert_select_matrix
            output = candidate_output * tmp_prob.unsqueeze(-1).unsqueeze(-1)
        else:
            output = candidate_output * expert_select_matrix.unsqueeze(-1).unsqueeze(-1)
        experts_output = torch.sum(output, dim=1) # [bz*num_beams-1, 32, 768]

        import pdb; pdb.set_trace()

        ####################
        ### universal expert
        ####################
        uni_output = forward_expert(x_uniexpert, self.num_experts-1) # [bz, 32, 768]

        ####################
        ### Combine expert
        ####################
        output = list()
        for i in range(batch_size):
            expert_tmp = experts_output[i*self.num_route_beam: i*self.num_route_beam+self.num_route_beam,:,:]
            combine_tmp = torch.cat((expert_tmp, uni_output[i].unsqueeze(0)))
            output.append(combine_tmp)
        final_output = torch.cat(output) # [bz*num_beam, 32 ,768]

        import pdb; pdb.set_trace()

        return final_output, beam_scores, expert_route, beam_idx, importance_loss
    
    def forward(self, x, attention_mask, beam_scores, expert_route, use_log=True):
        """
            if first_layer: x [bz, 32, 768]
            else: x [bz*num_beams, 32, 768]
        """
        if self.route_method == 'pre-route-uni':
            candidate_output, beam_scores, expert_route, beam_idx, importance_loss = self.forward_pre_route(x, beam_scores, expert_route, use_log=True)
        elif self.route_method in ['post-route-uni']:
            candidate_output, beam_scores, expert_route, beam_idx, importance_loss = self.forward_post_route_uni(x, beam_scores, expert_route, use_log=True)

        import pdb;pdb.set_trace()
        return candidate_output, beam_scores, expert_route, beam_idx, importance_loss




if __name__ == '__main__':

    import sys
    sys.path.append("/mnt/pfs-guan-ssai/nlu/wanghanzi/multimodal/PromptMoE")
    from minigpt4.models.QformerRouteMoE import BertConfig
    from minigpt4.models.QformerRouteMoE import FeedForward

    from minigpt4.models.moe.utils import (
        use_experts,
        moe_layer_judge,
    )
    vision_width = 1408
    cross_attention_freq = 2
    num_query_token = 32
    # init_QformerMoE
    config = BertConfig.from_pretrained("/mnt/pfs-guan-ssai/nlu/wanghanzi/models/bert-base-uncased")
    config.encoder_width = vision_width
    # insert cross-attention layer every other block
    config.add_cross_attention = True
    config.cross_attention_freq = cross_attention_freq
    config.query_length = num_query_token
    config.moebert_expert_num = 3
    config.moebert_num_beams = 3
    config.moebert_route_method = 'gate-sentence'
    config.moe_topk = 3
    config.use_balance_loss = False
    config.moe_weight_type = 'l2_norm'

    batch_size = 4
    x = torch.randn(batch_size, 32, 768)
    beam_scores, expert_route = None, None
    x1 = x
    x2 = x
    x3 = x
    beam_scores1, expert_route1 = None, None
    beam_scores2, expert_route2 = None, None

    for layer_num in [6, 8, 10]:
        layer_judge = moe_layer_judge(layer_num)
        ffn = FeedForward(config)

        # experts_post = RouteMoELayer(
        #             hidden_size=768,
        #             expert=ffn,
        #             num_experts=config.moebert_expert_num,
        #             num_beams=config.moebert_num_beams,
        #             layer_judge = layer_judge,
        #             route_method = "post-route",
        #             weight_type="ffn_prob"
        #         )
        # layer_output = experts_post(x1, None, beam_scores1, expert_route1, False)
        # hidden_states2, beam_scores1, expert_route1, beam_idx, importance_loss = layer_output

        # print(beam_scores1)
        # print(expert_route1)
        # print(beam_idx)
        # print(importance_loss)
        # x1 = hidden_states2

        experts_post = UniRouteMoELayer(
                    hidden_size=768,
                    expert=ffn,
                    num_experts=config.moebert_expert_num,
                    num_beams=config.moebert_num_beams,
                    layer_judge = layer_judge,
                    route_method = "post-route-uni",
                    weight_type="ffn_prob"
                )
        layer_output = experts_post(x2, None, beam_scores2, expert_route2, False)
        hidden_states3, beam_scores2, expert_route2, beam_idx2, importance_loss2 = layer_output

        print(beam_scores2)
        print(expert_route2)
        print(beam_idx2)
        print(importance_loss2)
        x2 = hidden_states3

        print("------------------------------------")
        import pdb; pdb.set_trace()

import copy
import pickle
import torch
import torch.nn as nn
import torch.nn.functional as F

class RouteMoELayer(nn.Module):
    def __init__(self, hidden_size, expert, num_experts, num_beams=2, layer_judge=None, route_method="pre-route"):
        # remove hash list
        nn.Module.__init__(self)
        self.num_experts = num_experts
        self.experts = nn.ModuleList([copy.deepcopy(expert) for i in range(num_experts)])
        self.num_beams = num_beams
        self.hidden_size = hidden_size
        self.layer_judge = layer_judge

        self.route_method = route_method
        if self.route_method == "pre-route":
            self.gate = nn.Linear(hidden_size, num_experts, bias=False).float()
        elif self.route_method == "post-route":
            gate = nn.Linear(hidden_size, 1, bias=False).float()
            self.gate = gate
            # self.gates = nn.ModuleList([copy.deepcopy(gate) for i in range(num_experts)])

    def forward_gate(self, x):
        """
            x : torch.Size([bz*num_beams, 32, 768]) or torch.Size([bz, 32, 768]) 
            prob_gate : torch.Size([bz*num_beams, num_experts])  or torch.Size([bz, num_experts]) 
        """
        attention_mask = torch.ones(x.shape[0], x.shape[1]).to(x.device)
        x_masked = x * attention_mask.unsqueeze(-1) # torch.Size([bz*num_beams, 32, 768])
        x_average = x_masked.sum(1) / attention_mask.unsqueeze(-1).sum(1) # torch.Size([bz*num_beams, 768])
        logits_gate = self.gate(x_average) # torch.Size([bz*num_beams, num_experts])
        prob_gate = F.softmax(logits_gate, dim=-1) #  torch.Size([bz*num_beams, num_experts])
        return prob_gate


    def beam_search(self, current_scores_log, beam_scores, expert_route, batch_size):
        if self.layer_judge=='first' and self.route_method=='pre-route':
            assert beam_scores==None and expert_route==None
            current_scores = torch.exp(current_scores_log)
            topk_values, gate = torch.topk(current_scores, self.num_beams, dim=1) # gate, 每个样本被分配的expert: torch.Size([bz, topk])
            beam_scores = topk_values.view(self.num_beams * batch_size) # torch.Size([bz * num_beams])
            expert_route = gate.view(self.num_beams * batch_size).unsqueeze(1) # torch.Size([bz * num_beams,1])
            beam_idx = None
        else:
            if self.layer_judge=='first' and self.route_method == 'post-route':
                batch_size = batch_size
                next_scores_raw1 = torch.exp(current_scores_log) # torch.Size([bz, num_experts])
            else:
                batch_size = int(batch_size // self.num_beams)
                next_scores_raw = current_scores_log + torch.log(beam_scores).unsqueeze(1)  # torch.Size([4*3, 5]) # 取log 之后，可以直接相加概率
                next_scores_exp = torch.exp(next_scores_raw)
                next_scores_raw1 = next_scores_exp.view(
                    batch_size, self.num_beams * self.num_experts
                )  # torch.Size([bz, num_beams*num_experts])

            next_scores, next_experts = torch.topk(next_scores_raw1, self.num_beams, dim=1, largest=True, sorted=True)
            # next_scores torch.Size([bz, num_beams])
            # next_tokens torch.Size([bz, num_beams])

            next_batch_beam = list()
            for batch_idx in range(batch_size):
                next_sent_beam = list()
                for rank, (expert_id, expert_score) in enumerate(
                    zip(next_experts[batch_idx], next_scores[batch_idx])
                ):
                    expert_id = expert_id.item()
                    beam_id = expert_id // self.num_experts
                    ex_id = expert_id % self.num_experts
                    effective_beam_id = batch_idx*self.num_beams + beam_id

                    next_sent_beam.append((expert_score, ex_id, effective_beam_id))
                next_batch_beam.extend(next_sent_beam)

            if self.layer_judge=='first' and self.route_method == 'post-route':
                beam_scores = next_scores.view(self.num_beams * batch_size) # torch.Size([bz * num_beams])
                expert_route = next_experts.view(self.num_beams * batch_size)
                beam_scores = beam_scores.new([x[0] for x in next_batch_beam])
                beam_experts = expert_route.new([x[1] for x in next_batch_beam]).unsqueeze(-1)
                beam_idx = expert_route.new([int(x[2]/self.num_beams) for x in next_batch_beam])
                expert_route = beam_experts
            else:
                beam_scores = beam_scores.new([x[0] for x in next_batch_beam])
                beam_experts = expert_route[:,-1].new([x[1] for x in next_batch_beam])
                beam_idx = expert_route[:,-1].new([x[2] for x in next_batch_beam])
                pre_route = expert_route[beam_idx,:]
                expert_route = torch.cat([pre_route, beam_experts.unsqueeze(1)], dim=-1)

        return beam_scores, expert_route, beam_idx
    
       
    def forward_expert_ffn(self, x, expert_select, beam_scores):
        """
            x_repeat : [bz*num_beams, 32,768]
            expert_select : [bz*num_beams]
        """
        # add_1212 l2_normalization
        # normalized_tensor = torch.nn.functional.normalize(beam_scores, p=2, dim=0) # L2 Normalization  torch.Size([bz, topk])
        # tmp_prob = normalized_tensor.unsqueeze(-1).unsqueeze(-1)

        outputs = list()
        for i in range(x.shape[0]):
            output_x = self.experts[expert_select[i]].forward(x[i])
            outputs.append(output_x.unsqueeze(0))
        candidate_output = torch.cat(outputs) 

        # candidate_output = candidate_output * tmp_prob
        return candidate_output # torch.Size([bz*num_beams, 32, 768])


    def forward_pre_route(self, x, beam_scores, expert_route, use_log=True):
        
        current_scores = self.forward_gate(x) # [bz*num_beams, 5]

        if use_log:
            current_scores_log = torch.log(current_scores) # 取log之后可以直接相加
        else:
            current_scores_log = current_scores

        batch_size, num_tokens = x.shape[0], x.shape[1]
        beam_scores, expert_route, beam_idx = self.beam_search(current_scores_log, beam_scores, expert_route, batch_size)

        current_expert_select = expert_route[:,-1]

        if self.layer_judge=='first': # expand first dim to batch_size * num_beams
            replicated_tensor = x.unsqueeze(1).expand(batch_size, self.num_beams, num_tokens, self.hidden_size)
            x = replicated_tensor.contiguous().view(-1, num_tokens, self.hidden_size) # [bz*num_beams, 32,768]

        candidate_output = self.forward_expert_ffn(x, current_expert_select, beam_scores) # [bz*num_beams, 32,768]
        
        return candidate_output, beam_scores, expert_route, beam_idx


    def forward_post_route(self, x, beam_scores, expert_route, use_log=True):
        
        attention_mask = torch.ones(x.shape[0], x.shape[1]).to(x.device)
        x_masked = x * attention_mask.unsqueeze(-1) # torch.Size([bz, 32, 768])
        
        def forward_expert(input_x, expert_idx):
            output_x = self.experts[expert_idx].forward(input_x)
            return output_x

        outputs = list()
        logits_gate_lst = list()
        for expert_idx in range(self.num_experts):
            output_x = forward_expert(x_masked, expert_idx)
            outputs.append(output_x.unsqueeze(0))
            output_x_aver = output_x.sum(1) / attention_mask.unsqueeze(-1).sum(1) # torch.Size([bz*num_beam, 768])
            # gate_score = self.gates[expert_idx](output_x_aver)
            gate_score = self.gate(output_x_aver)
            logits_gate_lst.append(gate_score)
        candidate_output = torch.cat(outputs) # torch.Size([num_expert, bz*num_beam, 32, 768])
        logits_gate = torch.cat(logits_gate_lst,dim=1)# torch.Size([bz*num_beam, num_expert])
        current_scores = F.softmax(logits_gate, dim=-1) # torch.Size([bz*num_beam, num_experts])

        if use_log:
            current_scores_log = torch.log(current_scores) # 取log之后可以直接相加
        else:
            current_scores_log = current_scores
        
        batch_size = x.shape[0] # bz*num_beam
        beam_scores, expert_route, beam_idx = self.beam_search(current_scores_log, beam_scores, expert_route, batch_size)
        # beam_scores torch.Size([bz*num_beam])
        # expert_route torch.Size([bz*num_beam, layer_n])
        current_select_expert = expert_route[:,-1]
        
        output = list()
        for i in range(beam_idx.shape[0]):
            b_idx = beam_idx[i]
            ex_idx = current_select_expert[i]
            ex_out = candidate_output[ex_idx, b_idx, :,:]
            output.append(ex_out.unsqueeze(0))

        final_output = torch.concat(output, dim=0)

        return final_output, beam_scores, expert_route, beam_idx


    def forward(self, x, attention_mask, beam_scores, expert_route, use_log=True):
        """
            if first_layer: x [bz, 32, 768]
            else: x [bz*num_beams, 32, 768]
        
        """
        if self.route_method == 'pre-route':
            candidate_output, beam_scores, expert_route, beam_idx = self.forward_pre_route(x, beam_scores, expert_route, use_log=True)
        elif self.route_method == "post-route":
            candidate_output, beam_scores, expert_route, beam_idx = self.forward_post_route(x, beam_scores, expert_route, use_log=True)

        return candidate_output, beam_scores, expert_route, beam_idx




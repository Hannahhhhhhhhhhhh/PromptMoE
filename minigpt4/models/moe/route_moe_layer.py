import copy
import pickle
import torch
import torch.nn as nn
import torch.nn.functional as F

class RouteMoELayer(nn.Module):
    def __init__(self, hidden_size, expert, num_experts, num_beams=2, layer_judge=None, route_method="pre-route", weight_type="ffn_prob"):
        # remove hash list
        nn.Module.__init__(self)
        self.num_experts = num_experts
        self.experts = nn.ModuleList([copy.deepcopy(expert) for i in range(num_experts)])
        self.num_beams = num_beams
        self.hidden_size = hidden_size
        self.layer_judge = layer_judge
        self.weight_type = weight_type

        self.route_method = route_method
        if self.route_method == "pre-route":
            self.gate = nn.Linear(hidden_size, num_experts, bias=False).float()
        elif self.route_method in ["post-route", "post-route-dp"]:
            gate = nn.Linear(hidden_size, 1, bias=False).float()
            self.gate = gate
            # self.gates = nn.ModuleList([copy.deepcopy(gate) for i in range(num_experts)])
        elif self.route_method in ['cls-route', 'cls-query-route', 'cls-cross-route']:
            self.gate = nn.Linear(hidden_size, 1, bias=False).float()


    def _importance_auxiliary_loss(self, prob_gate):
        # From VMOE
        # _importance_auxiliary_loss
        axis = tuple(range(prob_gate.ndim - 1))  # All except last.
        importance_per_expert = torch.sum(prob_gate, dim=axis)
        std_importance_per_expert = torch.std(importance_per_expert)
        mean_importance_per_expert = torch.mean(importance_per_expert)
        # Compute coefficient of variation (i.e. std/mean) squared.
        return (std_importance_per_expert / mean_importance_per_expert)**2

    def forward_gate(self, x):
        """
            x : torch.Size([bz*num_beams, 32, 768]) or torch.Size([bz, 32, 768]) 
            prob_gate : torch.Size([bz*num_beams, num_experts])  or torch.Size([bz, num_experts]) 
        """
        attention_mask = torch.ones(x.shape[0], x.shape[1]).to(x.device)
        x_masked = x * attention_mask.unsqueeze(-1) # torch.Size([bz*num_beams, 32, 768])
        # x_average = x_masked.sum(1) / attention_mask.unsqueeze(-1).sum(1) # torch.Size([bz*num_beams, 768])
        x_average = torch.mean(x_masked, dim=1) # torch.Size([bz*num_beams, 768])
        logits_gate = self.gate(x_average) # torch.Size([bz*num_beams, num_experts])
        prob_gate = F.softmax(logits_gate, dim=-1) #  torch.Size([bz*num_beams, num_experts])
        return prob_gate

    def dp_search(self, current_scores_log, beam_scores, expert_route, batch_size):
        if self.layer_judge=='first' and self.route_method in ['post-route-dp']:
            # current_scores_log torch.Size([bz, num_experts])
            assert beam_scores==None and expert_route==None
            current_scores = torch.exp(current_scores_log)
            topk_values, gate = torch.topk(current_scores, self.num_beams, dim=1) # gate, 每个样本被分配的expert: torch.Size([bz, topk])
            beam_scores = topk_values.view(self.num_beams * batch_size) # torch.Size([bz * num_beams])
            expert_route = gate.view(self.num_beams * batch_size).unsqueeze(1) # torch.Size([bz * num_beams,1])
            beam_idx = torch.tensor(range(self.num_beams * batch_size))

        else:
            batch_size = int(batch_size // self.num_beams)
            next_scores_raw = current_scores_log + torch.log(beam_scores).unsqueeze(1)  # torch.Size([4*3, 5]) # 取log 之后，可以直接相加概率
            next_scores_exp = torch.exp(next_scores_raw)

            next_scores_raw, next_experts_raw = torch.topk(next_scores_exp, 1, dim=1, largest=True, sorted=True)
            next_scores = next_scores_raw.view(batch_size, self.num_beams)
            next_experts = next_experts_raw.view(batch_size, self.num_beams)
            # next_scores, next_experts = torch.topk(current_scores_log, 1, dim=1, largest=True, sorted=True) # equal 等价
            # next_scores torch.Size([bz * num_beams, 1])
            # next_tokens torch.Size([bz * num_beams, 1])

            next_batch_beam = list()
            for batch_idx in range(batch_size):
                next_sent_beam = list()
                expert_id = next_experts[batch_idx]
                expert_score = next_scores[batch_idx]
                values, index = torch.topk(expert_score, self.num_beams, dim=0, largest=True, sorted=True)
                for i in range(self.num_beams):
                    beam_id = index[i].item()
                    ex_id = expert_id[beam_id].item()
                    effective_beam_id = batch_idx*self.num_beams + beam_id
                    next_sent_beam.append((values[i], ex_id, effective_beam_id))
                next_batch_beam.extend(next_sent_beam)

            beam_scores = beam_scores.new([x[0] for x in next_batch_beam])
            beam_experts = expert_route[:,-1].new([x[1] for x in next_batch_beam])
            beam_idx = expert_route[:,-1].new([x[2] for x in next_batch_beam])
            pre_route = expert_route[beam_idx,:]
            expert_route = torch.cat([pre_route, beam_experts.unsqueeze(1)], dim=-1)

        return beam_scores, expert_route, beam_idx
    
    def beam_search(self, current_scores_log, beam_scores, expert_route, batch_size):
        if self.layer_judge=='first' and self.route_method in ['pre-route', 'post-route', 'cls-route', 'cls-query-route', 'cls-cross-route']:
            # current_scores_log torch.Size([bz, num_experts])
            assert beam_scores==None and expert_route==None
            current_scores = torch.exp(current_scores_log)
            topk_values, gate = torch.topk(current_scores, self.num_beams, dim=1) # gate, 每个样本被分配的expert: torch.Size([bz, topk])
            beam_scores = topk_values.view(self.num_beams * batch_size) # torch.Size([bz * num_beams])
            expert_route = gate.view(self.num_beams * batch_size).unsqueeze(1) # torch.Size([bz * num_beams,1])
            beam_idx = torch.tensor(range(self.num_beams * batch_size))
            
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

            beam_scores = beam_scores.new([x[0] for x in next_batch_beam])
            beam_experts = expert_route[:,-1].new([x[1] for x in next_batch_beam])
            beam_idx = expert_route[:,-1].new([x[2] for x in next_batch_beam])
            pre_route = expert_route[beam_idx,:]
            expert_route = torch.cat([pre_route, beam_experts.unsqueeze(1)], dim=-1)

        return beam_scores, expert_route, beam_idx
    
    def forward_expert_ffn(self, x, expert_select, current_scores):
        """
            x_repeat : [bz*num_beams, 32,768]
            expert_select : [bz*num_beams]
            current_scores : [bz*num_beams, num_experts] / [bz, num_experts]
        """
        # add_1228 l2_normalization
        # normalized_tensor = torch.nn.functional.normalize(current_scores, p=2, dim=0) # L2 Normalization  torch.Size([bz, topk])
        # tmp_prob = normalized_tensor.unsqueeze(-1).unsqueeze(-1)
        # import pdb;pdb.set_trace()
        outputs = list()
        for i  in range(self.num_experts):
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
        return output # torch.Size([bz*num_beams, 32, 768])

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
            # output_x_aver = output_x.sum(1) / attention_mask.unsqueeze(-1).sum(1) # torch.Size([bz*num_beam, 768])
            output_x_aver = torch.mean(output_x, dim=1)
            # gate_score = self.gates[expert_idx](output_x_aver)
            gate_score = self.gate(output_x_aver)
            logits_gate_lst.append(gate_score)
            outputs.append(output_x.unsqueeze(0))

        candidate_output_raw = torch.cat(outputs) # torch.Size([num_expert, bz*num_beam, 32, 768])
        logits_gate = torch.cat(logits_gate_lst,dim=1)# torch.Size([bz*num_beam, num_expert])
        current_scores = F.softmax(logits_gate, dim=-1) # torch.Size([bz*num_beam, num_experts])

        if use_log:
            current_scores_log = torch.log(current_scores) # 取log之后可以直接相加
        else:
            current_scores_log = current_scores
        
        # importance loss
        importance_loss = self._importance_auxiliary_loss(current_scores)
        
        batch_size, num_tokens = x.shape[0], x.shape[1] # bz*num_beam

        if self.route_method == 'post-route':
            beam_scores, expert_route, beam_idx = self.beam_search(current_scores_log, beam_scores, expert_route, batch_size)
        elif self.route_method == 'post-route-dp':
            beam_scores, expert_route, beam_idx = self.dp_search(current_scores_log, beam_scores, expert_route, batch_size)

        # beam_scores torch.Size([bz*num_beam])
        # expert_route torch.Size([bz*num_beam, layer_n])
        current_select_expert = expert_route[:,-1]
        # current_select_expert torch.Size([bz*num_beam, 1])
        
        if self.layer_judge == 'first':
            replicated_tensor = candidate_output_raw.unsqueeze(2).expand(self.num_experts, batch_size, self.num_beams, num_tokens, self.hidden_size)
            candidate_output_raw = replicated_tensor.contiguous().view(self.num_experts, -1, num_tokens, self.hidden_size) # [bz*num_beams, 32,768]
            current_scores_t = current_scores.unsqueeze(1).expand(batch_size, self.num_beams, self.num_experts)
            current_scores = current_scores_t.contiguous().view(-1, self.num_experts) # [bz*num_beams, num_experts]
        
        candidate_output = candidate_output_raw.permute(1, 0, 2, 3)[beam_idx] # torch.Size([8, 2, 32, 768])
        expert_select_matrix = F.one_hot(current_select_expert, self.num_experts)
        if self.weight_type == 'ffn_prob':
            tmp_prob = current_scores[beam_idx] * expert_select_matrix
            output = candidate_output * tmp_prob.unsqueeze(-1).unsqueeze(-1)
        else:
            output = candidate_output * expert_select_matrix.unsqueeze(-1).unsqueeze(-1)
        final_output = torch.sum(output, dim=1)
        
        return final_output, beam_scores, expert_route, beam_idx, importance_loss
    
    def calculate_cls_gate_score(self, cls_hidden, output_x):

        if self.route_method == 'cls-route':
            # cls_hidden = [bz, 768]
            gate_score = self.gate(cls_hidden) # bz, 1
        elif self.route_method == 'cls-query-route': # add cls_hiddin on query_token mean pool hidden
            mean_output = torch.mean(output_x, dim=1) # bz, 768
            gate_score = self.gate(mean_output+cls_hidden) # bz, 1
        elif self.route_method == 'cls-cross-route':
            # cls_hidden as Q, output_x as K, V calculate scaled dot-product attention between Q and K and V
            # cls_hidden: bz, 768
            # output_x: bz, 32, 768
            Q = cls_hidden.unsqueeze(1) # bz, 1, 768
            K = output_x # bz, 32, 768
            V = output_x # bz, 32, 768
            # scaled dot-product attention
            QK = torch.matmul(Q, K.transpose(-1, -2)) / (K.size(-1) ** 0.5) # bz, 1, 32
            QK = F.softmax(QK, dim=-1) # bz, 1, 32
            gate_score = torch.matmul(QK, V) # bz, 1, 768
            gate_score = gate_score.squeeze(1) # bz, 768
            gate_score = self.gate(gate_score) # bz, 1
        return gate_score


    def forward_cls_route(self, x, beam_scores, expert_route, cls_hidden):
        attention_mask = torch.ones(x.shape[0], x.shape[1]).to(x.device)
        x_masked = x * attention_mask.unsqueeze(-1) # torch.Size([bz, 32, 768])

        def forward_expert(input_x, expert_idx):
            output_x = self.experts[expert_idx].forward(input_x)
            return output_x

        outputs = list()
        logits_gate_lst = list()
        for expert_idx in range(self.num_experts):
            output_x = forward_expert(x_masked, expert_idx) # bz, 32, 768

            gate_score = self.calculate_cls_gate_score(cls_hidden, output_x) # bz, 1

            logits_gate_lst.append(gate_score)
            outputs.append(output_x.unsqueeze(0))

        candidate_output_raw = torch.cat(outputs) # torch.Size([num_expert, bz*num_beam, 32, 768])
        logits_gate = torch.cat(logits_gate_lst,dim=1)# torch.Size([bz*num_beam, num_expert])
        current_scores = F.softmax(logits_gate, dim=-1) # torch.Size([bz*num_beam, num_experts])

        current_scores_log = torch.log(current_scores) # 取log之后可以直接相加
        
        # importance loss
        importance_loss = self._importance_auxiliary_loss(current_scores)
        
        batch_size, num_tokens = x.shape[0], x.shape[1] # bz*num_beam

        beam_scores, expert_route, beam_idx = self.beam_search(current_scores_log, beam_scores, expert_route, batch_size)

        # beam_scores torch.Size([bz*num_beam])
        # expert_route torch.Size([bz*num_beam, layer_n])
        current_select_expert = expert_route[:,-1]
        # current_select_expert torch.Size([bz*num_beam, 1])
        
        if self.layer_judge == 'first':
            replicated_tensor = candidate_output_raw.unsqueeze(2).expand(self.num_experts, batch_size, self.num_beams, num_tokens, self.hidden_size)
            candidate_output_raw = replicated_tensor.contiguous().view(self.num_experts, -1, num_tokens, self.hidden_size) # [bz*num_beams, 32,768]
            current_scores_t = current_scores.unsqueeze(1).expand(batch_size, self.num_beams, self.num_experts)
            current_scores = current_scores_t.contiguous().view(-1, self.num_experts) # [bz*num_beams, num_experts]
        
        candidate_output = candidate_output_raw.permute(1, 0, 2, 3)[beam_idx] # torch.Size([8, 2, 32, 768])
        expert_select_matrix = F.one_hot(current_select_expert, self.num_experts)
        if self.weight_type == 'ffn_prob':
            tmp_prob = current_scores[beam_idx] * expert_select_matrix
            output = candidate_output * tmp_prob.unsqueeze(-1).unsqueeze(-1)
        else:
            output = candidate_output * expert_select_matrix.unsqueeze(-1).unsqueeze(-1)
        final_output = torch.sum(output, dim=1)

        return final_output, beam_scores, expert_route, beam_idx, importance_loss


    def forward(self, x, attention_mask, beam_scores, expert_route, cls_hidden=None):
        """
            if first_layer: x [bz, 32, 768]
            else: x [bz*num_beams, 32, 768]
        
        """
        if self.route_method == 'pre-route':
            candidate_output, beam_scores, expert_route, beam_idx, importance_loss = self.forward_pre_route(x, beam_scores, expert_route, use_log=True)
        elif self.route_method in ['post-route', 'post-route-dp']:
            candidate_output, beam_scores, expert_route, beam_idx, importance_loss = self.forward_post_route(x, beam_scores, expert_route, use_log=True)
        elif self.route_method in ['cls-route', 'cls-query-route', 'cls-cross-route']:
            candidate_output, beam_scores, expert_route, beam_idx, importance_loss = self.forward_cls_route(x, beam_scores, expert_route, cls_hidden)
        else:
            assert("route method should in pre-route, post-route, post-route-dp")
        return candidate_output, beam_scores, expert_route, beam_idx, importance_loss

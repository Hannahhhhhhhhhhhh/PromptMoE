"""
 Copyright (c) 2022, salesforce.com, inc.
 All rights reserved.
 SPDX-License-Identifier: BSD-3-Clause
 For full license text, see the LICENSE file in the repo root or https://opensource.org/licenses/BSD-3-Clause
"""

from collections import OrderedDict
import json
import os
import random
import torch

from PIL import Image

from minigpt4.datasets.datasets.vqa_datasets import VQADataset  #, VQAEvalDataset


class __DisplMixin:
    def displ_item(self, index):
        sample, ann = self.__getitem__(index), self.annotation[index]
        return OrderedDict(
            {
                "file": ann["image"],
                "question": ann["question"],
                "question_id": ann["question_id"],
                "direct_answers": "; ".join(ann["direct_answers"]),
                "choices": "; ".join(ann["choices"]),
                "correct_choice": ann["choices"][ann["correct_choice_idx"]],
                "image": sample["image"],
            }
        )


class AOKVQADataset(VQADataset, __DisplMixin):
    def __init__(self, vis_processor, text_processor, vis_root, ann_paths):
        super().__init__(vis_processor, text_processor, vis_root, ann_paths)

        self.instruction_pool =[   
            '{}',
            'Q: {} A: ',
            'Based on the image, respond to this question with a short answer: {}',
            '{} A short answer to the question is ',
            'Question: {} Short answer:',
        ]

        exist_annotation = []
        for ann in self.annotation:
            # image_path = os.path.join(self.vis_root, ann["image"].split('/')[-1])
            image_path = os.path.join(self.vis_root, ann["image"])
            if os.path.exists(image_path):
                exist_annotation.append(ann)
        self.annotation = exist_annotation
        self.source = 'aokvqa'

    def get_data(self, index):
        ann = self.annotation[index]

        # image_path = os.path.join(self.vis_root, ann["image"].split('/')[-1])
        image_path = os.path.join(self.vis_root, ann["image"])
        image = Image.open(image_path).convert("RGB")

        image = self.vis_processor(image)
        question = self.text_processor(ann["question"])

        answer_key = "direct_answers"

        answer_weight = {}
        for answer in ann[answer_key]:
            if answer in answer_weight.keys():
                answer_weight[answer] += 1 / len(ann[answer_key])
            else:
                answer_weight[answer] = 1 / len(ann[answer_key])

        answers = list(answer_weight.keys())
        weights = list(answer_weight.values())

        answer = random.choices(answers, weights=weights, k=1)[0]  # random sample an answer according to weights

        return {
            "image": image,
            "image_id": ann["image"],
            "question": question,
            "answer": answer,
        }

    def __getitem__(self, index):
        data = self.get_data(index)
        question = self.text_processor(data["question"])

        answer = self.text_processor(data['answer'])
        q_input = question
        llm_input = random.choice(self.instruction_pool).format(question)

        return {
            "image": data['image'],
            "image_id": data["image_id"],
            "q_input": q_input,
            "llm_input": llm_input,
            "text_input": question,
            "text_output": answer,
            "answer": answer,
            "source": 'aokvqa',
        }


class AOKVQGDataset(AOKVQADataset):

    def __init__(self, vis_processor, text_processor, vis_root, ann_paths):
        super().__init__(vis_processor, text_processor, vis_root, ann_paths)
        self.instruction_pool = [
            'Given the image, generate a question whose answer is: {}',
            'Based on the image, provide a question with the answer: {}',
            'Given the visual representation, create a question for which the answer is "{}"',
            'From the image provided, craft a question that leads to the reply: {}',
            'Considering the picture, come up with a question where the answer is: {}',
            'Taking the image into account, generate an question that has the answer: {}'
        ]

    def __getitem__(self, index):
        data = self.get_data(index)
        instruction = random.choice(self.instruction_pool).format(data['answer'])

        return {
            "image": data['image'],
            "instruction_input": instruction,
            "answer": data['question'],
        }

import os
import logging
import warnings

from minigpt4.common.registry import registry
from minigpt4.datasets.builders.base_dataset_builder import BaseDatasetBuilder
from minigpt4.datasets.datasets.laion_dataset import LaionDataset
from minigpt4.datasets.datasets.cc_sbu_dataset import CCSBUDataset, CCSBUAlignDataset
from minigpt4.datasets.datasets.text_caps import TextCapDataset, TextCapEvalDataset
from minigpt4.datasets.datasets.text_vqa_dataset import TextVQADataset, TextVQAEvalDataset
from minigpt4.datasets.datasets.llava_dataset import LlavaDetailDataset, LlavaReasonDataset, LlavaConversationDataset, LlavaMixDataset, LlavaPretrainDataset
from minigpt4.datasets.datasets.unnatural_instruction import UnnaturalDataset
from minigpt4.datasets.datasets.multitask_conversation import MultiTaskConversationDataset
from minigpt4.datasets.datasets.flickr import GroundedDetailDataset,CaptionToObjectDataset,PhraseToObjectDataset
from minigpt4.datasets.datasets.gqa_datasets import GQADataset, GQAEvalDataset
from minigpt4.datasets.datasets.aok_vqa_datasets import AOKVQADataset, AOKVQAEvalDataset
from minigpt4.datasets.datasets.coco_vqa_datasets import COCOVQADataset, COCOVQAEvalDataset
from minigpt4.datasets.datasets.ok_vqa_datasets import OKVQADataset, OKVQAEvalDataset
from minigpt4.datasets.datasets.ocrvqa_dataset import OCRVQADataset
from minigpt4.datasets.datasets.coco_caption import COCOCapDataset, COCOCapEvalDataset

@registry.register_builder("multitask_conversation")
class MultitaskConversationBuilder(BaseDatasetBuilder):
    train_dataset_cls = MultiTaskConversationDataset
    DATASET_CONFIG_DICT = {
        "default": "configs/datasets/multitask_conversation/default.yaml",
    }

    def build_datasets(self):
        # at this point, all the annotations and image/videos should be all downloaded to the specified locations.
        logging.info("[multitask_conversation]: Building datasets...")
        self.build_processors()
        build_info = self.config.build_info
        datasets = dict()

        # create datasets
        dataset_cls = self.train_dataset_cls
        datasets['train'] = dataset_cls(
            vis_processor=self.vis_processors["train"],
            text_processor=self.text_processors["train"],
            ann_path=build_info.ann_path,
            vis_root=build_info.image_path,
        )

        return datasets


@registry.register_builder("unnatural_instruction")
class UnnaturalInstructionBuilder(BaseDatasetBuilder):
    train_dataset_cls = UnnaturalDataset
    DATASET_CONFIG_DICT = {
        "default": "configs/datasets/nlp/unnatural_instruction.yaml",
    }

    def build_datasets(self):
        # at this point, all the annotations and image/videos should be all downloaded to the specified locations.
        logging.info("[unnatural_instruction]: Building datasets...")
        self.build_processors()
        build_info = self.config.build_info
        datasets = dict()

        # create datasets
        dataset_cls = self.train_dataset_cls
        datasets['train'] = dataset_cls(
            text_processor=self.text_processors["train"],
            ann_path=build_info.ann_path,
        )
        print("{} Length: {}".format(dataset_cls.__name__, len(datasets['train']))) # print class name

        return datasets



@registry.register_builder("llava_detail")
class LlavaDetailBuilder(BaseDatasetBuilder):
    train_dataset_cls = LlavaDetailDataset
    DATASET_CONFIG_DICT = {
        "default": "configs/datasets/llava/detail.yaml",
    }

    def build_datasets(self):
        # at this point, all the annotations and image/videos should be all downloaded to the specified locations.
        logging.info("[llava_detail]: Building datasets...")
        self.build_processors()
        build_info = self.config.build_info
        datasets = dict()

        # create datasets
        dataset_cls = self.train_dataset_cls
        datasets['train'] = dataset_cls(
            vis_processor=self.vis_processors["train"],
            text_processor=self.text_processors["train"],
            ann_path=build_info.ann_path,
            vis_root=build_info.image_path,
        )
        print("{} Length: {}".format(dataset_cls.__name__, len(datasets['train']))) # print class name

        return datasets
    
@registry.register_builder("llava_reason")
class LlavaReasonBuilder(BaseDatasetBuilder):
    train_dataset_cls = LlavaReasonDataset
    DATASET_CONFIG_DICT = {
        "default": "configs/datasets/llava/reason.yaml",
    }

    def build_datasets(self):
        # at this point, all the annotations and image/videos should be all downloaded to the specified locations.
        logging.info("[llava_reason]: Building datasets...")
        self.build_processors()
        build_info = self.config.build_info
        datasets = dict()

        # create datasets
        dataset_cls = self.train_dataset_cls
        datasets['train'] = dataset_cls(
            vis_processor=self.vis_processors["train"],
            text_processor=self.text_processors["train"],
            ann_path=build_info.ann_path,
            vis_root=build_info.image_path,
        )
        print("{} Length: {}".format(dataset_cls.__name__, len(datasets['train']))) # print class name

        return datasets

@registry.register_builder("llava_pretrain")
class LlavaPretrainBuilder(BaseDatasetBuilder):
    train_dataset_cls = LlavaPretrainDataset
    DATASET_CONFIG_DICT = {
        "default": "configs/datasets/llava/pretrain_cap.yaml",
    }

    def build_datasets(self):
        # at this point, all the annotations and image/videos should be all downloaded to the specified locations.
        logging.info("[llava_pretrain]: Building datasets...")
        self.build_processors()
        build_info = self.config.build_info
        datasets = dict()

        # create datasets
        dataset_cls = self.train_dataset_cls
        datasets['train'] = dataset_cls(
            vis_processor=self.vis_processors["train"],
            text_processor=self.text_processors["train"],
            ann_path=build_info.ann_path,
            vis_root=build_info.image_path,
        )
        print("{} Length: {}".format(dataset_cls.__name__, len(datasets['train']))) # print class name

        return datasets


@registry.register_builder("llava_conversation")
class LlavaReasonBuilder(BaseDatasetBuilder):
    train_dataset_cls = LlavaConversationDataset
    DATASET_CONFIG_DICT = {
        "default": "configs/datasets/llava/conversation.yaml",
    }

    def build_datasets(self):
        # at this point, all the annotations and image/videos should be all downloaded to the specified locations.
        logging.info("[llava_conversation]: Building datasets...")
        self.build_processors()
        build_info = self.config.build_info
        datasets = dict()

        # create datasets
        dataset_cls = self.train_dataset_cls
        datasets['train'] = dataset_cls(
            vis_processor=self.vis_processors["train"],
            text_processor=self.text_processors["train"],
            ann_path=build_info.ann_path,
            vis_root=build_info.image_path,
        )
        print("{} Length: {}".format(dataset_cls.__name__, len(datasets['train']))) # print class name

        return datasets

@registry.register_builder("llava_mix")
class LlavaMixBuilder(BaseDatasetBuilder):
    train_dataset_cls = LlavaMixDataset
    DATASET_CONFIG_DICT = {
        "default": "configs/datasets/llava/mix.yaml",
        "mix_coco_gqa": "configs/datasets/mix_vqa/mix_vqa.yaml",
    }

    def build_datasets(self):
        # at this point, all the annotations and image/videos should be all downloaded to the specified locations.
        logging.info("[llava_mix]: Building datasets...")
        self.build_processors()
        build_info = self.config.build_info
        datasets = dict()

        # create datasets
        dataset_cls = self.train_dataset_cls
        vis_roots = {
            'coco':build_info.image_path_coco,
            'gqa':build_info.image_path_gqa,
            'ocr':build_info.image_path_ocr,
            'text':build_info.image_path_text,
            # 'vg':build_info.image_path_vg,
        }
        datasets['train'] = dataset_cls(
            vis_processor=self.vis_processors["train"],
            text_processor=self.text_processors["train"],
            ann_path=build_info.ann_path,
            vis_root=vis_roots,
        )
        print("{} Length: {}".format(dataset_cls.__name__, len(datasets['train']))) # print class name

        # vis_roots = {
        #     'coco':'/mnt/pfs-guan-ssai/nlu/dingyifeng/data/COCO/train2014',
        #     'gqa':'/mnt/pfs-guan-ssai/nlu/wanghanzi/data/GQA/images',
        #     'ocr':'/mnt/pfs-guan-ssai/nlu/wanghanzi/data/OCRVQA/images',
        #     'text':'/mnt/pfs-guan-ssai/nlu/wanghanzi/data/TextVQA/train_images',
        #     # 'vg':build_info.image_path_vg,
        # }
        
        return datasets


class AllRefCOCOBuilder(BaseDatasetBuilder):

    def build_datasets(self):
        # at this point, all the annotations and image/videos should be all downloaded to the specified locations.
        logging.info("[AllRefCOCOBuilder]: Building datasets...")
        self.build_processors()

        build_info = self.config.build_info
        image_path = build_info.image_path
        ann_path = build_info.ann_path

        datasets = dict()

        if not os.path.exists(image_path):
            warnings.warn("image path {} does not exist.".format(image_path))
        if not os.path.exists(ann_path):
            warnings.warn("ann path {} does not exist.".format(ann_path))

        # create datasets
        dataset_cls = self.train_dataset_cls
        datasets['train'] = dataset_cls(
            vis_processor=self.vis_processors["train"],
            text_processor=self.text_processors["train"],
            ann_path=ann_path,
            vis_root=image_path,
            dataset=build_info.dataset,
            splitBy=build_info.splitBy
        )

        return datasets
    

@registry.register_builder("textcaps_caption")
class TextcapCaptionBuilder(BaseDatasetBuilder):
    train_dataset_cls = TextCapDataset
    eval_dataset_cls = TextCapEvalDataset

    DATASET_CONFIG_DICT = {"default": "configs/datasets/textcaps/caption.yaml"}

    def _download_ann(self):
        pass

    def _download_vis(self):
        pass

@registry.register_builder("text_vqa")
class TextVQABuilder(BaseDatasetBuilder):
    train_dataset_cls = TextVQADataset
    eval_dataset_cls = TextVQAEvalDataset

    DATASET_CONFIG_DICT = {"default": "configs/datasets/textvqa/vqa.yaml"}
    
    def _download_ann(self):
        pass

    def _download_vis(self):
        pass

@registry.register_builder("coco_vqa")
class COCOVQABuilder(BaseDatasetBuilder):
    train_dataset_cls = COCOVQADataset
    eval_dataset_cls = COCOVQAEvalDataset

    DATASET_CONFIG_DICT = {
        "default": "configs/datasets/coco/defaults_vqa.yaml",
        "vqa_v2_eval": "configs/datasets/coco/defaults_vqa_eval.yaml",
        "vqa_v2_part": "configs/datasets/coco/defaults_vqa_part.yaml",
    }

@registry.register_builder("ok_vqa")
class OKVQABuilder(COCOVQABuilder):
    train_dataset_cls = OKVQADataset
    eval_dataset_cls = OKVQAEvalDataset

    DATASET_CONFIG_DICT = {
        "default": "configs/datasets/okvqa/defaults.yaml",
        "ok_vqa_eval": "configs/datasets/okvqa/eval.yaml",
    }


@registry.register_builder("aok_vqa")
class AOKVQABuilder(BaseDatasetBuilder):
    train_dataset_cls = AOKVQADataset
    eval_dataset_cls = AOKVQAEvalDataset

    DATASET_CONFIG_DICT = {"default": "configs/datasets/aokvqa/defaults.yaml"}


@registry.register_builder("gqa")
class GQABuilder(BaseDatasetBuilder):
    train_dataset_cls = GQADataset
    eval_dataset_cls = GQAEvalDataset

    DATASET_CONFIG_DICT = {
        "balanced_sft_raw": "configs/datasets/gqa/balanced_sft_raw.yaml",
        "balanced_sft_raw_eval":"configs/datasets/gqa/balanced_sft_raw_eval.yaml",
        "balanced_sft_raw_part":"configs/datasets/gqa/balanced_sft_raw_part.yaml",
    }


@registry.register_builder("flickr_grounded_caption")
class GroundedCaptionBuilder(BaseDatasetBuilder):
    train_dataset_cls = GroundedDetailDataset
    DATASET_CONFIG_DICT = {
        "default": "configs/datasets/flickr/default.yaml",
    }

    def build_datasets(self):
        # at this point, all the annotations and image/videos should be all downloaded to the specified locations.
        logging.info("[flickr_grounded_caption]: Building datasets...")
        self.build_processors()
        build_info = self.config.build_info
        datasets = dict()

        # create datasets
        dataset_cls = self.train_dataset_cls
        datasets['train'] = dataset_cls(
            vis_processor=self.vis_processors["train"],
            text_processor=self.text_processors["train"],
            ann_path=build_info.ann_path,
            vis_root=build_info.image_path,
        )

        return datasets


@registry.register_builder("flickr_CaptionToPhrase")
class CaptionToPhraseBuilder(BaseDatasetBuilder):
    train_dataset_cls = CaptionToObjectDataset
    DATASET_CONFIG_DICT = {
        "default": "configs/datasets/flickr/caption_to_phrase.yaml",
    }

    def build_datasets(self):
        # at this point, all the annotations and image/videos should be all downloaded to the specified locations.
        logging.info("[flickr_CaptionToPhrase]: Building datasets...")
        self.build_processors()
        build_info = self.config.build_info
        datasets = dict()

        # create datasets
        dataset_cls = self.train_dataset_cls
        datasets['train'] = dataset_cls(
            vis_processor=self.vis_processors["train"],
            text_processor=self.text_processors["train"],
            ann_path=build_info.ann_path,
            vis_root=build_info.image_path,
        )

        return datasets

@registry.register_builder("flickr_ObjectToPhrase")
class CaptionToPhraseBuilder(BaseDatasetBuilder):
    train_dataset_cls = PhraseToObjectDataset
    DATASET_CONFIG_DICT = {
        "default": "configs/datasets/flickr/object_to_phrase.yaml",
    }

    def build_datasets(self):
        # at this point, all the annotations and image/videos should be all downloaded to the specified locations.
        logging.info("[flickr_ObjectToPhrase]: Building datasets...")
        self.build_processors()
        build_info = self.config.build_info
        datasets = dict()

        # create datasets
        dataset_cls = self.train_dataset_cls
        datasets['train'] = dataset_cls(
            vis_processor=self.vis_processors["train"],
            text_processor=self.text_processors["train"],
            ann_path=build_info.ann_path,
            vis_root=build_info.image_path,
        )

        return datasets


class DocumentVQABuilder(BaseDatasetBuilder):
    def _download_ann(self):
        pass

    def _download_vis(self):
        pass

    def build(self):
        self.build_processors()
        build_info = self.config.build_info

        datasets = dict()
        split = "train"

        dataset_cls = self.train_dataset_cls
        datasets[split] = dataset_cls(
            vis_processor=self.vis_processors[split],
            text_processor=self.text_processors[split],
            vis_root=build_info.image_path,
            ann_path=build_info.ann_path
        )
        print("{} Length: {}".format(dataset_cls.__name__, len(datasets['train']))) # print class name
        
        return datasets
    

@registry.register_builder("ocrvqa")
class OCRVQABuilder(DocumentVQABuilder):
    train_dataset_cls = OCRVQADataset
    DATASET_CONFIG_DICT = {"default": "configs/datasets/ocrvqa/ocrvqa.yaml"}


@registry.register_builder("cc_sbu")
class CCSBUBuilder(BaseDatasetBuilder):
    train_dataset_cls = CCSBUDataset

    DATASET_CONFIG_DICT = {"default": "configs/datasets/cc_sbu/defaults.yaml"}

    def _download_ann(self):
        pass

    def _download_vis(self):
        pass

    def build(self):
        self.build_processors()

        build_info = self.config.build_info

        datasets = dict()
        split = "train"

        # create datasets
        # [NOTE] return inner_datasets (wds.DataPipeline)
        dataset_cls = self.train_dataset_cls
        datasets[split] = dataset_cls(
            vis_processor=self.vis_processors[split],
            text_processor=self.text_processors[split],
            location=build_info.storage,
        ).inner_dataset

        return datasets


@registry.register_builder("laion")
class LaionBuilder(BaseDatasetBuilder):
    train_dataset_cls = LaionDataset

    DATASET_CONFIG_DICT = {"default": "configs/datasets/laion/defaults.yaml"}

    def _download_ann(self):
        pass

    def _download_vis(self):
        pass

    def build(self):
        self.build_processors()

        build_info = self.config.build_info

        datasets = dict()
        split = "train"

        # create datasets
        # [NOTE] return inner_datasets (wds.DataPipeline)
        dataset_cls = self.train_dataset_cls
        datasets[split] = dataset_cls(
            vis_processor=self.vis_processors[split],
            text_processor=self.text_processors[split],
            location=build_info.storage,
        ).inner_dataset

        return datasets



@registry.register_builder("coco_caption")
class COCOCapBuilder(BaseDatasetBuilder):
    train_dataset_cls = COCOCapDataset
    eval_dataset_cls = COCOCapEvalDataset
    
    DATASET_CONFIG_DICT = {
        "default": "configs/datasets/coco/caption.yaml",
        "coco_cap_eval": "configs/datasets/coco/caption_eval.yaml",
    }



@registry.register_builder("cc_sbu_align")
class CCSBUAlignBuilder(BaseDatasetBuilder):
    train_dataset_cls = CCSBUAlignDataset

    DATASET_CONFIG_DICT = {
        "default": "configs/datasets/cc_sbu/align.yaml",
    }

    def build_datasets(self):
        # at this point, all the annotations and image/videos should be all downloaded to the specified locations.
        logging.info("Building datasets...")
        self.build_processors()

        build_info = self.config.build_info
        storage_path = build_info.storage

        datasets = dict()

        if not os.path.exists(storage_path):
            warnings.warn("storage path {} does not exist.".format(storage_path))

        # create datasets
        dataset_cls = self.train_dataset_cls
        datasets['train'] = dataset_cls(
            vis_processor=self.vis_processors["train"],
            text_processor=self.text_processors["train"],
            ann_paths=[os.path.join(storage_path, 'filter_cap.json')],
            vis_root=os.path.join(storage_path, 'image'),
        )

        return datasets

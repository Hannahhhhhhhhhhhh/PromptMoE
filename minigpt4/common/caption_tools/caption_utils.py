
from collections import defaultdict
from pycocoevalcap.eval import COCOEvalCap
import json

class COCO_Annotation:
    def __init__(self, annotation_file):
        self.coco_cn_file = annotation_file
        self.imgToAnns = self.build_imgToAnns()
    
    def build_imgToAnns(self):
        imgToAnns = defaultdict(list)
        with open(self.coco_cn_file, "r", encoding="UTF-8") as fin:
            for line in fin:
                line = line.strip()
                temp = eval(line)
                annotations = temp['annotations']
                for ann in annotations:
                    image_id = str(ann['image_id']).zfill(6)
                    imgToAnns[image_id].append({'image_id':image_id,'caption':ann['caption'],'image': ann['image_id']})
        return imgToAnns
    
    def getImgIds(self):
        return self.imgToAnns.keys()  

class COCO_Result:
    def __init__(self,result_file):
        self.coco_cn_file = result_file
        self.imgToAnns = self.build_imgToAnns()
    
    def build_imgToAnns(self):
        imgToAnns = dict()
        data = json.load(open(self.coco_cn_file, "r"))
        for d in data:
            tmp = {
                'image_id':d['question_id'][-6:],
                'caption':d['answer']
            }
            imgToAnns[d['question_id'][-6:]] = [tmp]
        return imgToAnns
    
def coco_caption_eval(coco_gt_root, results_file, split_name):
    files = {
        "val":"/mnt/pfs-guan-ssai/nlu/wanghanzi/data/COCO_Cap/coco_karpathy_val_gt.json",
        "test":"/mnt/pfs-guan-ssai/nlu/wanghanzi/data/COCO_Cap/coco_karpathy_test_gt.json"
    }

    # create coco object and coco_result object
    annotation_file = files[split_name]
    coco = COCO_Annotation(annotation_file)
    coco_result = COCO_Result(results_file)

    # create coco_eval object by taking coco and coco_result
    coco_eval = COCOEvalCap(coco, coco_result)

    # evaluate on a subset of images by setting
    # coco_eval.params['image_id'] = coco_result.getImgIds()
    # please remove this line when evaluating the full validation set
    # coco_eval.params['image_id'] = coco_result.getImgIds()

    # evaluate results
    # SPICE will take a few minutes the first time, but speeds up due to caching
    coco_eval.evaluate()

    # print output evaluation scores
    for metric, score in coco_eval.eval.items():
        print(f"{metric}: {score:.3f}")

    return coco_eval



class TextCap_Annotation:
    def __init__(self, annotation_file):
        self.anno_file = annotation_file
        self.imgToAnns = self.build_imgToAnns()
    
    def build_imgToAnns(self):
        imgToAnns = defaultdict(list)
        annotations = json.load(open(self.anno_file,"r"))['data']
        for ann in annotations:
            image_id = str(ann['image_name'])
            imgToAnns[image_id].append({
                'image_id':image_id,
                # 'caption':ann['reference_strs'],
                'caption':ann['caption_str'],
                'image': ann['image_path']
                })
        return imgToAnns
    
    def getImgIds(self):
        return self.imgToAnns.keys() 

class TextCap_Result:
    def __init__(self,result_file):
        self.result_file = result_file
        self.imgToAnns = self.build_imgToAnns()
    
    def build_imgToAnns(self):
        imgToAnns = dict()
        data = json.load(open(self.result_file, "r"))
        for d in data:
            tmp = {
                'image_id':d['question_id'], # actually image_id
                'caption':d['answer']
            }
            imgToAnns[d['question_id']] = [tmp]
        return imgToAnns
    
    
def textcaps_caption_eval(annotation_file, results_file):

    # create coco object and coco_result object
    anno = TextCap_Annotation(annotation_file)
    result = TextCap_Result(results_file)

    # create coco_eval object by taking coco and coco_result
    text_eval = COCOEvalCap(anno, result)

    # SPICE will take a few minutes the first time, but speeds up due to caching
    text_eval.evaluate()

    # print output evaluation scores
    for metric, score in text_eval.eval.items():
        print(f"{metric}: {score:.3f}")

    return text_eval

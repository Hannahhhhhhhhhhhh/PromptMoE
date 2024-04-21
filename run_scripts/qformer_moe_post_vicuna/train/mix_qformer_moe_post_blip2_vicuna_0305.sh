GPUS_PER_NODE=4
export MASTER_PORT=8526
export CUDA_VISIBLE_DEVICES=4,5,6,7
python -m torch.distributed.run --nproc_per_node=${GPUS_PER_NODE} --master_port=${MASTER_PORT} train.py --cfg-path minigpt4/projects/qformer_moe_post_vicuna/train/mix_qformer_moe_post_blip2_vicuna7b_route.yaml


# python train.py --cfg-path minigpt4/projects/qformer_moe_post_vicuna/train/mix_qformer_moe_post_blip2_vicuna7b_cosine_route.yaml
# python train.py --cfg-path minigpt4/projects/qformer_moe_post_vicuna/train/mix_qformer_moe_post_blip2_vicuna7b_cls_route.yaml
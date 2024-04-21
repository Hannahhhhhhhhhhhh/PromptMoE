GPUS_PER_NODE=4
export MASTER_PORT=8572
export OMP_NUM_THREADS=2
export CUDA_VISIBLE_DEVICES=0,1,6,7
python -m torch.distributed.run --nproc_per_node=${GPUS_PER_NODE} --master_port=${MASTER_PORT} train.py --cfg-path minigpt4/projects/qformer_moe_route_universal_vicuna/train/mix7_qformer_moe_route_uni_blip2_vicuna7b_0325.yaml

# export CUDA_VISIBLE_DEVICES=3
# export MASTER_PORT=8530
# python train.py --cfg-path  minigpt4/projects/qformer_moe_route_universal_vicuna/train/mix_qformer_moe_route_uni_blip2_vicuna7b_0317.yaml
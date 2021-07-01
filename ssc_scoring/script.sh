#!/bin/bash
#SBATCH --partition=gpu-medium
#SBATCH --gres=gpu:2
#SBATCH --cpus-per-gpu=6
##SBATCH -t 7-00:00:00
#SBATCH --mem-per-gpu=90G
#SBATCH --mail-type=end
#SBATCH --mail-user=jiajingnan2222@gmail.com

eval "$(conda shell.bash hook)"

conda activate py37

job_id=$SLURM_JOB_ID
#echo $SLURM_JOB_ID
#echo $job_id
#echo $(hostname)

cp script.sh slurmlogs/slurm-${job_id}.sh
cp run.py slurmlogs/slurm-${job_id}_run.py  # backup main file
cp set_args.py slurmlogs/slurm-${job_id}_set_args.py  # backup setting

#idx=0; export CUDA_VISIBLE_DEVICES=$idx; stdbuf -oL python -u run.py 2>slurmlogs/slurm-${job_id}_$idx.err 1>slurmlogs/slurm-${job_id}_$idx.out --outfile=slurmlogs/slurm-${job_id}_$idx --hostname=$(hostname)  --eval_id=1045  --fold=4 &

#idx=0; export CUDA_VISIBLE_DEVICES=$idx; stdbuf -oL python -u run.py 2>slurmlogs/slurm-${job_id}_$idx.err 1>slurmlogs/slurm-${job_id}_$idx.out --outfile=slurmlogs/slurm-${job_id}_$idx --hostname=$(hostname) --epochs=1000 --net='vgg11_bn' --sys=1 --sampler=0 --sys_pro_in_0=0.5 --sys_ratio=0.0 --mode='train' --fold=2 --remark="vgg11, sys, batchsize=10, ellipselenth=100+200, nosampler, gen_gg_as_retp correctlys" &
#idx=1; export CUDA_VISIBLE_DEVICES=$idx; stdbuf -oL python -u run.py 2>slurmlogs/slurm-${job_id}_$idx.err 1>slurmlogs/slurm-${job_id}_$idx.out --outfile=slurmlogs/slurm-${job_id}_$idx --hostname=$(hostname) --epochs=1000 --net='vgg11_bn' --sys=1 --sampler=0 --sys_pro_in_0=0.5 --sys_ratio=0.0 --mode='train' --fold=4 --remark="vgg11, sys, batchsize=10, ellipselenth=100+200, nosampler, gen_gg_as_retp correctlys" &


idx=0; export CUDA_VISIBLE_DEVICES=$idx; stdbuf -oL python -u run_pos.py 2>slurmlogs/slurm-${job_id}_$idx.err 1>slurmlogs/slurm-${job_id}_$idx.out --outfile=slurmlogs/slurm-${job_id}_$idx --hostname="$(hostname)" --net="vgg11_3d" --fine_level=5 --fold=3 --remark="fine_level" &
idx=1; export CUDA_VISIBLE_DEVICES=$idx; stdbuf -oL python -u run_pos.py 2>slurmlogs/slurm-${job_id}_$idx.err 1>slurmlogs/slurm-${job_id}_$idx.out --outfile=slurmlogs/slurm-${job_id}_$idx --hostname="$(hostname)" --net="vgg11_3d" --fine_level=5 --fold=4 --remark="fine_level" &

wait




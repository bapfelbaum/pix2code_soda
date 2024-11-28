#!/bin/bash

python -m torch.distributed.launch --nproc_per_node=2 --use_env pix2seq/main.py --pix2seq_lr --large_scale_jitter --rand_target --coco_path "soda/" --output_dir "soda/output/"$@
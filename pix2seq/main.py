# Copyright (c) Facebook, Inc. and its affiliates. All Rights Reserved

from rtpt import RTPT
import argparse
import datetime
import json
import random
import time
from pathlib import Path

import numpy as np
import torch
from torch.utils.data import DataLoader, DistributedSampler

import datasets
import util.misc as utils
from datasets import build_dataset, get_coco_api_from_dataset
from engine import evaluate, train_one_epoch

# from models import build_model
from playground import build_all_model
from timm.utils import NativeScaler


def get_args_parser():
    parser = argparse.ArgumentParser("Set transformer detector", add_help=False)
    parser.add_argument("--lr", default=1e-3, type=float)
    parser.add_argument("--lr_backbone", default=1e-4, type=float)
    parser.add_argument("--weight_decay", default=0.05, type=float)
    parser.add_argument("--batch_size", default=16, type=int)
    parser.add_argument("--epochs", default=100, type=int)
    parser.add_argument("--lr_drop", default=200, type=int)
    parser.add_argument(
        "--clip_max_norm", default=0.1, type=float, help="gradient clipping max norm"
    )
    parser.add_argument(
        "--amp_train", action="store_true", help="amp fp16 training or not"
    )
    parser.add_argument("--eval_epoch", default=5, type=int)

    # Pix2Seq
    parser.add_argument(
        "--model", type=str, default="pix2seq", help="specify the model from playground"
    )
    parser.add_argument(
        "--pix2seq_lr", action="store_true", help="use warmup linear drop lr"
    )
    parser.add_argument(
        "--large_scale_jitter", action="store_true", help="large scale jitter"
    )
    parser.add_argument(
        "--rand_target",
        action="store_true",
        help="randomly permute the sequence of input targets",
    )
    parser.add_argument(
        "--pred_eos",
        action="store_true",
        help="use eos token instead of predicting 100 objects",
    )

    # * Backbone
    parser.add_argument(
        "--backbone",
        default="resnet18",
        type=str,
        help="Name of the convolutional backbone to use",
    )
    parser.add_argument(
        "--dilation",
        action="store_true",
        help="If true, we replace stride with dilation in the last convolutional block (DC5)",
    )
    parser.add_argument(
        "--position_embedding",
        default="sine",
        type=str,
        choices=("sine", "learned"),
        help="Type of positional embedding to use on top of the image features",
    )

    # * Transformer
    parser.add_argument(
        "--enc_layers",
        default=6,
        type=int,
        help="Number of encoding layers in the transformer",
    )
    parser.add_argument(
        "--dec_layers",
        default=6,
        type=int,
        help="Number of decoding layers in the transformer",
    )
    parser.add_argument(
        "--dim_feedforward",
        default=1024,
        type=int,
        help="Intermediate size of the feedforward layers in the transformer blocks",
    )
    parser.add_argument(
        "--hidden_dim",
        default=256,
        type=int,
        help="Size of the embeddings (dimension of the transformer)",
    )
    parser.add_argument(
        "--dropout", default=0.1, type=float, help="Dropout applied in the transformer"
    )
    parser.add_argument(
        "--nheads",
        default=8,
        type=int,
        help="Number of attention heads inside the transformer's attentions",
    )
    parser.add_argument("--pre_norm", action="store_true")

    # * Loss coefficients
    parser.add_argument(
        "--eos_coef",
        default=0.1,
        type=float,
        help="Relative classification weight of the no-object class",
    )

    # dataset parameters
    parser.add_argument("--dataset_file", default="clevr")
    parser.add_argument("--coco_path", default="../data/pattern_free_clevr", type=str)
    parser.add_argument("--coco_panoptic_path", type=str)
    parser.add_argument("--remove_difficult", action="store_true")

    parser.add_argument(
        "--output_dir",
        default="./train_results",
        help="path where to save, empty for no saving",
    )
    parser.add_argument(
        "--device", default="cuda", help="device to use for training / testing"  # todo
    )
    parser.add_argument("--seed", default=42, type=int)
    parser.add_argument("--resume", default="", help="resume from checkpoint")
    parser.add_argument(
        "--start_epoch", default=0, type=int, metavar="N", help="start epoch"
    )
    parser.add_argument("--eval", default="", action="store_true")
    parser.add_argument("--num_workers", default=0, type=int)

    # distributed training parameters
    parser.add_argument(
        "--world_size", default=1, type=int, help="number of distributed processes"
    )
    parser.add_argument(
        "--dist_url", default="env://", help="url used to set up distributed training"
    )
    return parser

def get_free_gpu (min_memory_mb=20480): #TODO added dynamic gpu fetching logic, looks for gpu with 20gig 
    free_gpus=[]
    for i in range(torch.cuda.device_count()):
        stats = torch.cuda.memory_stats(i)
        free_mem = stats.get("active.all.current", 0)
        if free_mem / (1024*1024) >= min_memory_mb:
            free_gpus.append(i)
    if not free_gpus:
        raise RuntimeError("Currently no GPU with enough free memory available, consider using another device or using multiple gpus!")
    return free_gpus[0]

def main(args, rtpt=None):
    utils.init_distributed_mode(args)
    print("git:\n  {}\n".format(utils.get_sha()))

    device = torch.device(args.device)

    # fix the seed for reproducibility
    seed = args.seed + utils.get_rank()
    torch.manual_seed(seed)
    np.random.seed(seed)
    random.seed(seed)

    model, criterion, postprocessors = build_all_model[args.model](args)
    model.to(device)

    model_without_ddp = torch.nn.DataParallel(model) #test changed from model
    if args.distributed:
        model = torch.nn.parallel.DistributedDataParallel(model, device_ids=[args.gpu])
        model_without_ddp = model.module
    n_parameters = sum(p.numel() for p in model.parameters() if p.requires_grad)
    print("number of params:", n_parameters)

    param_dicts = [
        {
            "params": [
                p
                for n, p in model_without_ddp.named_parameters()
                if "backbone" not in n and p.requires_grad
            ]
        },
        {
            "params": [
                p
                for n, p in model_without_ddp.named_parameters()
                if "backbone" in n and p.requires_grad
            ],
            "lr": args.lr_backbone,
        },
    ]
    optimizer = torch.optim.AdamW(
        param_dicts, lr=args.lr, weight_decay=args.weight_decay
    )
    if args.pix2seq_lr:
        lr_scheduler = utils.WarmupLinearDecayLR(
            optimizer,
            warmup_factor=0.01,
            warmup_iters=10,
            warmup_method="linear",
            end_epoch=args.epochs,
            final_lr_factor=0.01,
        )
    else:
        lr_scheduler = torch.optim.lr_scheduler.StepLR(optimizer, args.lr_drop)
    loss_scaler = NativeScaler() if args.amp_train else utils.NoScaler()

    dataset_train = build_dataset(image_set="train", args=args)
    dataset_val = build_dataset(image_set="val", args=args)

    if args.distributed:
        sampler_train = DistributedSampler(dataset_train)
        sampler_val = DistributedSampler(dataset_val, shuffle=False)
    else:
        sampler_train = torch.utils.data.RandomSampler(dataset_train)
        sampler_val = torch.utils.data.SequentialSampler(
            dataset_val
        )  # TODO change to dataset_val

    batch_sampler_train = torch.utils.data.BatchSampler(
        sampler_train, args.batch_size, drop_last=True
    )

    data_loader_train = DataLoader(
        dataset_train,
        batch_sampler=batch_sampler_train,
        collate_fn=utils.collate_fn,
        num_workers=args.num_workers,
    )
    data_loader_val = DataLoader(
        dataset_val,  # TODO change to dataset_val
        args.batch_size,
        sampler=sampler_val,
        drop_last=False,
        collate_fn=utils.collate_fn,
        num_workers=args.num_workers,
    )

    if args.dataset_file == "coco_panoptic":
        # We also evaluate AP during panoptic training, on original coco DS
        coco_val = datasets.coco.build("val", args)
        base_ds = get_coco_api_from_dataset(coco_val)
    else:
        base_ds = get_coco_api_from_dataset(dataset_val)  # TODO change to dataset_val

    output_dir = Path(args.output_dir)
    cur_ap = max_ap = 0.0
    if args.resume:
        if args.resume.startswith("https"):
            checkpoint = torch.hub.load_state_dict_from_url(
                args.resume, map_location="cpu", check_hash=True
            )
        else:
            checkpoint = torch.load(args.resume, map_location="cpu")

        model_without_ddp.load_state_dict(checkpoint["model"])
        print("Pretrained model loaded")
        if (
            not args.eval
            and "optimizer" in checkpoint
            and "lr_scheduler" in checkpoint
            and "epoch" in checkpoint
        ):
            optimizer.load_state_dict(checkpoint["optimizer"])
            lr_scheduler.load_state_dict(checkpoint["lr_scheduler"])
            args.start_epoch = checkpoint["epoch"] + 1
            print("Startepoch: ", args.start_epoch)
        if "ap" in checkpoint:
            cur_ap = checkpoint["ap"]
            max_ap = checkpoint["max_ap"]
            args.start_epoch = checkpoint["epoch"] + 1
            # args.start_epoch = 1 # TODO remove later
            # cur_ap = 0
            # max_ap = 0
            print("Epoch: ", args.start_epoch)

    if args.eval:
        test_stats, coco_evaluator = evaluate(
            model,
            criterion,
            postprocessors,
            data_loader_val,
            base_ds,
            device,
            args.output_dir,
        )
        if args.output_dir:
            utils.save_on_master(
                coco_evaluator.coco_eval["bbox"].eval, output_dir / "eval.pth"
            )
        return

    print("Start training")
    start_time = time.time()
    for epoch in range(args.start_epoch, args.epochs):
        if args.distributed:
            sampler_train.set_epoch(epoch)
        train_stats = train_one_epoch(
            model,
            criterion,
            data_loader_train,
            optimizer,
            device,
            epoch,
            loss_scaler,
            rtpt,
            args.clip_max_norm,
            amp_train=args.amp_train,
            rand_target=args.rand_target,
        )
        print(f"Scheduler State: {lr_scheduler.state_dict()}") #debug added might need to update lr scheduler
        print(f"last Epoch: {lr_scheduler.last_epoch}") #end debug
        print(f"End epoch: {lr_scheduler.end_epoch}") #debug
        if epoch == 50: 
            lr_scheduler = utils.WarmupLinearDecayLR(
                optimizer,
                warmup_factor=0.01,
                warmup_iters=10,
                warmup_method="linear",
                end_epoch=args.epochs,
                final_lr_factor=0.01,
            ) #remove me


        lr_scheduler.step()
        rtpt.step()

        if (
            epoch % args.eval_epoch == 0
            or epoch == (args.lr_drop - 1)
            or epoch == (args.epochs - 1)
        ):
            test_stats, coco_evaluator = evaluate(
                model,
                criterion,
                postprocessors,
                data_loader_val,
                base_ds,
                device,
                args.output_dir,
            )

            log_stats = {
                **{f"train_{k}": v for k, v in train_stats.items()},
                **{f"test_{k}": v for k, v in test_stats.items()},
                "epoch": epoch,
                "n_parameters": n_parameters,
            }
            cur_ap = test_stats["coco_eval_bbox"][0]
        else:
            log_stats = {
                **{f"train_{k}": v for k, v in train_stats.items()},
                "epoch": epoch,
                "n_parameters": n_parameters,
            }
            test_stats = coco_evaluator = None

        if args.output_dir:
            checkpoint_paths = [output_dir / "checkpoint.pth"]
            # extra checkpoint before LR drop and every 10 epochs
            if (epoch + 1) % args.lr_drop == 0 or (epoch + 1) % 10 == 0:
                checkpoint_paths.append(output_dir / f"checkpoint{epoch:04}.pth")
            if cur_ap > max_ap:
                checkpoint_paths.append(output_dir / "checkpoint_best.pth")
                max_ap = cur_ap
            for checkpoint_path in checkpoint_paths:
                utils.save_on_master(
                    {
                        "model": model_without_ddp.state_dict(),
                        "optimizer": optimizer.state_dict(),
                        "lr_scheduler": lr_scheduler.state_dict(),
                        "epoch": epoch,
                        "args": args,
                        "ap": cur_ap,
                        "max_ap": max_ap,
                    },
                    checkpoint_path,
                )

        if args.output_dir and utils.is_main_process():
            with (output_dir / "log.txt").open("a") as f:
                f.write(json.dumps(log_stats) + "\n")

            # for evaluation logs
            if coco_evaluator is not None:
                (output_dir / "eval").mkdir(exist_ok=True)
                if "bbox" in coco_evaluator.coco_eval:
                    filenames = ["latest.pth"]
                    if epoch % 50 == 0:
                        filenames.append(f"{epoch:03}.pth")
                    for name in filenames:
                        torch.save(
                            coco_evaluator.coco_eval["bbox"].eval,
                            output_dir / "eval" / name,
                        )
        import gc                
        gc.collect() #test added
        torch.cuda.empty_cache() #test added
    


    total_time = time.time() - start_time
    total_time_str = str(datetime.timedelta(seconds=int(total_time)))
    print("Training time {}".format(total_time_str))


if __name__ == "__main__":
    # Create RTPT object
    rtpt = RTPT(name_initials="XX", experiment_name="Pix2Seq", max_iterations=150) #changed to 150

    # Start the RTPT tracking
    rtpt.start()

    parser = argparse.ArgumentParser(
        "Pix2Seq training and evaluation script", parents=[get_args_parser()]
    )
    args = parser.parse_args()
    if args.output_dir:
        Path(args.output_dir).mkdir(parents=True, exist_ok=True)

    # train
    args.large_scale_jitter = True
    args.rand_target = True

    args.dataset_file = "soda"
    args.coco_path = "soda/"

    args.output_dir = "soda/output/"
    #args.resume = "pix2seq/train_results/checkpoint_e299_ap370.pth"

    args.lr = 3e-4
    args.lr_backbone = 3e-5
    args.epochs = 150
    args.batch_size = 4
    args.num_workers = 8

    #added block to look for proper gpu
    try: 
        gpu_id = get_free_gpu()
        device = torch.device(f"cuda:{gpu_id}")
        print(f"Using GPU {gpu_id} with likely sufficient memory.")
    except RuntimeError as e:
        print(e)
        device = torch.device("cuda")
        print("Falling back to default cuda, will probably crash due to lack of memory")
    main(args, rtpt)

from pathlib import Path

import torch
import torch.utils.data
import torchvision
from pycocotools import mask as coco_mask

import datasets.transforms as T


class SODADetection(torchvision.datasets.CocoDetection):
    def __init__(
        self,
        img_folder,
        ann_file,
        transforms,
        return_masks,
        large_scale_jitter,
        image_set,
    ):
        super(SODADetection, self).__init__(img_folder, ann_file)
        self._transforms = transforms
        self.prepare = ConvertCocoPolysToMask(return_masks)
        self.large_scale_jitter = large_scale_jitter
        self.image_set = image_set

    def __getitem__(self, idx):
        img, target = super(SODADetection, self).__getitem__(idx)
        image_id = self.ids[idx]
        target = {"image_id": image_id, "annotations": target}
        img, target = self.prepare(img, target)
        if self._transforms is not None:
            if self.large_scale_jitter and self.image_set == "train":
                img1, target1 = self._transforms(img, target)
                img2, target2 = self._transforms(img, target)
                return img1, img2, target1, target2
            else:
                img, target = self._transforms(img, target)
                return img, target
        return img, target


def convert_coco_poly_to_mask(segmentations, height, width):
    masks = []
    for polygons in segmentations:
        rles = coco_mask.frPyObjects(polygons, height, width)
        mask = coco_mask.decode(rles)
        if len(mask.shape) < 3:
            mask = mask[..., None]
        mask = torch.as_tensor(mask, dtype=torch.uint8)
        mask = mask.any(dim=2)
        masks.append(mask)
    if masks:
        masks = torch.stack(masks, dim=0)
    else:
        masks = torch.zeros((0, height, width), dtype=torch.uint8)
    return masks


class ConvertCocoPolysToMask(object):
    def __init__(self, return_masks=False):
        self.return_masks = return_masks

    def __call__(self, image, target):
        w, h = image.size

        image_id = target["image_id"]
        image_id = torch.tensor([image_id])

        anno = target["annotations"]

        anno = [obj for obj in anno if "iscrowd" not in obj or obj["iscrowd"] == 0]

        boxes = [obj["bbox"] for obj in anno]
        # guard against no boxes via resizing
        boxes = torch.as_tensor(boxes, dtype=torch.float32).reshape(-1, 4)
        boxes[:, 2:] += boxes[:, :2]
        boxes[:, 0::2].clamp_(min=0, max=w)
        boxes[:, 1::2].clamp_(min=0, max=h)

        classes = [obj["category_id"] for obj in anno]
        classes = torch.tensor(classes, dtype=torch.int64)

        if self.return_masks:
            segmentations = [obj["segmentation"] for obj in anno]
            masks = convert_coco_poly_to_mask(segmentations, h, w)

        keypoints = None
        if anno and "keypoints" in anno[0]:
            keypoints = [obj["keypoints"] for obj in anno]
            keypoints = torch.as_tensor(keypoints, dtype=torch.float32)
            num_keypoints = keypoints.shape[0]
            if num_keypoints:
                keypoints = keypoints.view(num_keypoints, -1, 3)

        keep = (boxes[:, 3] > boxes[:, 1]) & (boxes[:, 2] > boxes[:, 0])
        boxes = boxes[keep]
        classes = classes[keep]
        if self.return_masks:
            masks = masks[keep]
        if keypoints is not None:
            keypoints = keypoints[keep]

        target = {}
        target["boxes"] = boxes
        target["labels"] = classes
        if self.return_masks:
            target["masks"] = masks

            polygons = [torch.tensor(obj["segmentation"][0]) for obj in anno]
            num_per_polygon = torch.tensor(
                [p.shape[0] for p in polygons], dtype=torch.int64
            )
            new_polygons = torch.zeros([len(polygons), max(num_per_polygon)])
            for gt_i, (np, p) in enumerate(zip(num_per_polygon, polygons)):
                new_polygons[gt_i, :np] = p
            target["polygons"] = new_polygons
            target["valid_pol_idx"] = num_per_polygon

        target["image_id"] = image_id
        if keypoints is not None:
            target["keypoints"] = keypoints

        # for conversion to coco api
        area = torch.tensor([obj["area"] for obj in anno])
        iscrowd = torch.tensor(
            [obj["iscrowd"] if "iscrowd" in obj else 0 for obj in anno]
        )
        target["area"] = area[keep]
        target["iscrowd"] = iscrowd[keep]

        target["orig_size"] = torch.as_tensor([int(h), int(w)])
        target["size"] = torch.as_tensor([int(h), int(w)])

        return image, target


def make_coco_transforms(image_set, args):
    normalize = T.Compose(
        [T.ToTensor(), T.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])]
    )

    scales = [480, 512, 544, 576, 608, 640, 672, 704, 736, 768, 800]

    if image_set == "train":
        if args.large_scale_jitter:
            return T.Compose(
                [
                    T.RandomHorizontalFlip(),
                    T.LargeScaleJitter(
                        output_size=1333, aug_scale_min=0.3, aug_scale_max=2.0
                    ),
                    T.RandomDistortion(0.5, 0.5, 0.5, 0.5),
                    normalize,
                ]
            )
        else:
            return T.Compose(
                [
                    T.RandomHorizontalFlip(),
                    T.RandomSelect(
                        T.RandomResize(scales, max_size=1333),
                        T.Compose(
                            [
                                T.RandomResize([400, 500, 600]),
                                T.RandomSizeCrop(384, 600),
                                T.RandomResize(scales, max_size=1333),
                            ]
                        ),
                    ),
                    normalize,
                ]
            )

    if image_set == "val" or image_set in ["true", "false"]:
        if args.large_scale_jitter:
            return T.Compose(
                [
                    T.LargeScaleJitter(
                        output_size=1333, aug_scale_min=1.0, aug_scale_max=1.0
                    ),
                    normalize,
                ]
            )
        else:
            return T.Compose(
                [
                    T.RandomResize([800], max_size=1333),
                    normalize,
                ]
            )

    raise ValueError(f"unknown {image_set}")

def make_id_transform(image_set, args): #test idea
    return T.Compose(
        [T.ToTensor(), T.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])]
    )


def build(image_set, args):
    root = Path(args.coco_path)
    assert root.exists(), f"provided data path {root} does not exist"
    mode = "instances"
    PATHS = {
        "train": (root / "train/images", root / "train" / f"{mode}.json"),
        "val": (root / "test/images", root / "test" / f"{mode}.json"),
    }

    img_folder, ann_file = PATHS[image_set]
    dataset = CLEVRDetection(
        img_folder,
        ann_file,
        transforms=make_coco_transforms(image_set, args),
        return_masks=False,
        large_scale_jitter=args.large_scale_jitter,
        image_set=image_set,
    )
    return dataset

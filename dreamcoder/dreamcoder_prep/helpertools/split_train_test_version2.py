import json
import os
import random

def sample_json_entries(input_file, output_file, sample_size):
    # Load the JSON data from the input file
    with open(input_file, 'r') as f:
        data = json.load(f)

    # Ensure the structure contains the necessary keys
    if "images" not in data or "annotations" not in data or "categories" not in data:
        raise ValueError("The JSON structure is missing required keys: 'images', 'annotations', or 'categories'.")
    
    images = data["images"]
    annotations = data["annotations"]
    categories = data["categories"]

    # Create a mapping from image_id to its annotations
    annotation_map = {}
    for annotation in annotations:
        image_id = annotation.get('image_id')
        if image_id not in annotation_map:
            annotation_map[image_id] = []
        annotation_map[image_id].append(annotation)

    # Sample random images
    sampled_images = random.sample(images, min(sample_size, len(images)))

    # Prepare the output structure
    output_data = {
        "type": data.get("type", "instance"),
        "images": [],
        "annotations": [],
        "categories": categories
    }

    # Collect annotations and image metadata for sampled images
    for image in sampled_images:
        image_id = image.get('id')
        output_data['images'].append(image)
        
        # Add annotations for the current image_id
        if image_id in annotation_map:
            output_data['annotations'].extend(annotation_map[image_id])

    # Write the output data to the output file
    with open(output_file, 'w') as f:
        json.dump(output_data, f, indent=4)

# Example usage
# sample_json_entries('input.json', 'output.json', 5)

def split_json(input_file, split_type, split_size):
    """
    Splits an annotation JSON file into smaller parts based on the specified split type and size.

    Args:
        input_file (str): Path to the input JSON file.
        split_type (str): "absolute" to split after a fixed number of images, "percentage" for percentage-based splits.
        split_size (int or float): The number of images (if split_type is "absolute") or percentage of images (if split_type is "percentage").
    """
    # Load the JSON data from the input file
    with open(input_file, 'r') as f:
        data = json.load(f)
    
    # Ensure the structure contains the necessary keys
    if "images" not in data or "annotations" not in data or "categories" not in data:
        raise ValueError("The JSON structure is missing required keys: 'images', 'annotations', or 'categories'.")
    
    images = data["images"]
    annotations = data["annotations"]
    categories = data["categories"]

    # Determine split size based on the split type
    if split_type == "percentage":
        if not (0 < split_size <= 100):
            raise ValueError("Percentage split size must be between 0 and 100.")
        split_count = int(len(images) * (split_size / 100.0))
    elif split_type == "absolute":
        if not (0 < split_size <= len(images)):
            raise ValueError(f"Absolute split size must be between 1 and the total number of images ({len(images)}).")
        split_count = split_size
    else:
        raise ValueError("Invalid split_type. Use 'absolute' or 'percentage'.")
    
    # Split the images and create new JSON files for each part
    part_number = 1
    for start_index in range(0, len(images), split_count):
        images_part = images[start_index:start_index + split_count]
        image_ids_part = {img["id"] for img in images_part}
        annotations_part = [ann for ann in annotations if ann["image_id"] in image_ids_part]

        part_data = {
            "type": data.get("type", "instance"),
            "images": images_part,
            "annotations": annotations_part,
            "categories": categories  # Keep all categories in all parts
        }

        # Create the output file name based on the input file name and split details
        base_name = os.path.splitext(os.path.basename(input_file))[0]
        output_file = f"{base_name}_split_{start_index + split_count}.json"

        # Save the split to a new JSON file
        with open(output_file, 'w') as f:
            json.dump(part_data, f, indent=4)
        
        print(f"Created: {output_file}")
        part_number += 1

# Example usage
#split_json("train_split_500_split_20.json", "absolute", 5)
input = "train.json"
output = "sampled_annotations.json"
samplesize = 500
sample_json_entries(input,output,samplesize)

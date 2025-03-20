import os
import json
from PIL import Image, ImageDraw, ImageFont

# Function to draw bounding boxes and labels on the image
def draw_annotations(image, annotations, categories):
    draw = ImageDraw.Draw(image)
    for ann in annotations:
        bbox = ann["bbox"]
        category_id = ann["category_id"]
        category_name = categories.get(category_id, "unknown")
        x, y, w, h = bbox

        # Set color based on category
        color = "red" if category_name == "ignore" else "blue"

        # Draw the bounding box
        draw.rectangle([x, y, x + w, y + h], outline=color, width=3)

        # Add label
        label = f"{category_name} (ID: {ann['id']})"
        draw.text((x, y - 10), label, fill="yellow")

# Main function to process all images in a directory
def overlay_annotations(imagepath, annotation_path, outputpath=None):
    # Load annotations from the JSON file
    with open(annotation_path, 'r') as f:
        annotation_data = json.load(f)

    # Ensure necessary keys exist in the annotation file
    if "images" not in annotation_data or "annotations" not in annotation_data or "categories" not in annotation_data:
        raise ValueError("The annotation JSON is missing required keys: 'images', 'annotations', or 'categories'.")

    images = {img["id"]: img["file_name"] for img in annotation_data["images"]}
    annotations = annotation_data["annotations"]
    categories = {cat["id"]: cat["name"] for cat in annotation_data["categories"]}

    # Organize annotations by image_id
    annotations_by_image = {}
    for ann in annotations:
        image_id = ann["image_id"]
        if image_id not in annotations_by_image:
            annotations_by_image[image_id] = []
        annotations_by_image[image_id].append(ann)

    # Output path handling
    if outputpath and not os.path.exists(outputpath):
        os.makedirs(outputpath)

    # Process each image in the directory
    for image_id, file_name in images.items():
        input_image_path = os.path.join(imagepath, file_name)
        if not os.path.isfile(input_image_path):
            print(f"Image file '{file_name}' not found in the directory. Skipping.")
            continue

        # Load the image
        image = Image.open(input_image_path)

        # Get the corresponding annotations
        image_annotations = annotations_by_image.get(image_id, [])

        # Draw annotations on the image
        draw_annotations(image, image_annotations, categories)

        # Save the annotated image with a new name
        output_file_name = os.path.splitext(file_name)[0] + "_with_annotations.jpg"
        output_image_path = os.path.join(outputpath if outputpath else ".", output_file_name)
        image.save(output_image_path)
        print(f"Annotated image saved to: {output_image_path}")

# Example usage
imagepath = "/home/bapfelbaum/pix2code/Test/SODA-D/Images"  # Directory containing images
annotation_path = "Trainingsplit_500_20/train_split_500_split_100.json"  # Annotation file path
outputpath = "/annotated_images"  # Directory to save annotated images (optional)

overlay_annotations(imagepath, annotation_path)#, outputpath)

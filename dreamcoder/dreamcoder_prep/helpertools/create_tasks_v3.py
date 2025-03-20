import os
import json

def create_annotations_json(input_file_positive, input_file_negative, output_folder_name):
    # Load the positive input JSON file
    with open(input_file_positive, 'r') as f:
        data_positive = json.load(f)

    # Load the negative input JSON file
    with open(input_file_negative, 'r') as f:
        data_negative = json.load(f)

    # Create the output folder structure
    os.makedirs(output_folder_name, exist_ok=True)
    true_folder = os.path.join(output_folder_name, 'true')
    false_folder = os.path.join(output_folder_name, 'false')
    os.makedirs(true_folder, exist_ok=True)
    os.makedirs(false_folder, exist_ok=True)

    # Function to convert bbox format and create output annotations
    def process_annotations(data, folder):
        for image in data['images']:
            image_id = image['id']
            annotations_for_image = [
                {
                    'boxes': [
                        annotation['bbox'][0],  # x
                        annotation['bbox'][1],  # y
                        annotation['bbox'][0] + annotation['bbox'][2],  # xmax
                        annotation['bbox'][1] + annotation['bbox'][3]   # ymax
                    ],
                    'labels': annotation['category_id']
                }
                for annotation in data['annotations']
                if annotation['image_id'] == image_id and annotation['ignore'] == 0
            ]

            # Create a new JSON file for the image in the specified folder
            if annotations_for_image:
                output_file_path = os.path.join(folder, f"{image_id:05d}.json")
                with open(output_file_path, 'w') as out_f:
                    json.dump({'annotations': annotations_for_image}, out_f, indent=4)

    # Process annotations for positive examples
    process_annotations(data_positive, true_folder)

    # Process annotations for negative examples
    process_annotations(data_negative, false_folder)

if __name__ == "__main__":
    # Example usage
    input_file = 'annotations_filtered_by_traffic_sign_right-of_vehicle'  # Replace with your actual input file
    input_file_positive = os.path.splitext(input_file)[0] + '_positive.json'
    input_file_negative = os.path.splitext(input_file)[0] + '_negative.json'
    output_folder_name = os.path.splitext(os.path.basename(input_file))[0]
    
    create_annotations_json(input_file_positive, input_file_negative, output_folder_name)


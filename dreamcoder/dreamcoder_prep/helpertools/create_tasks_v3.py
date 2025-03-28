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
    def process_annotations(data, folder, maxdim=None):
        for image in data['images']:
            image_id = image['id']
            imagemax = max(image['height'], image['width'])
            factor = maxdim/imagemax if type(maxdim) is int else 1
            annotations_for_image = [
                {
                    'boxes': [
                        annotation['bbox'][0] if type(maxdim) is not int else round(annotation['bbox'][0] * factor),  # xmin
                        annotation['bbox'][1] if type(maxdim) is not int else round(annotation['bbox'][1] * factor),  # ymin
                        annotation['bbox'][0] + annotation['bbox'][2] if type(maxdim) is not int else round((annotation['bbox'][0] + annotation['bbox'][2]) * factor),  # xmax
                        annotation['bbox'][1] + annotation['bbox'][3] if type(maxdim) is not int else round((annotation['bbox'][1] + annotation['bbox'][3]) * factor)  # ymax
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
    process_annotations(data_positive, true_folder, 500)

    # Process annotations for negative examples
    process_annotations(data_negative, false_folder, 500)

if __name__ == "__main__":
    # Example usage
    input_file = 'annotations_filtered_by_traffic_sign_right-of_vehicle'  # Replace with your actual input file
    if len(sys.argv) > 1 and not sys.argv[1].isdigit(): #grab input filename
        input_file = sys.argv[1]
        args = sys.argv[2:]
    else:
        args = sys.argv[1:]
    input_file_positive = os.path.splitext(input_file)[0] + '_positive.json'
    input_file_negative = os.path.splitext(input_file)[0] + '_negative.json'
    output_folder_name = os.path.splitext(os.path.basename(input_file))[0]
    
    create_annotations_json(input_file_positive, input_file_negative, output_folder_name)


    
    
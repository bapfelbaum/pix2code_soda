import json
import sys

def load_json(file_path):
    """Load JSON data from a file."""
    with open(file_path, 'r') as f:
        return json.load(f)         
              
def filter_relations(image_data, relation_type=None, obj_type1=None, obj_type2=None):
    """Filter relations based on optional criteria."""
    matching_relations = []
    object_categories = image_data['categories']  # Use the correct dictionary structure

    for relation in image_data['relations']:
        if len(relation) < 3:  # Skip malformed relations
            continue
        
        rel_type, obj1_id, obj2_id = relation[:3]  # Unpack relation structure

        if relation_type and rel_type != relation_type and relation_type != "*": #added wildcard
            continue
        # Convert object types to integers for comparison
        obj_type1 = int(obj_type1) if obj_type1 is not None else None
        obj_type2 = int(obj_type2) if obj_type2 is not None else None

        if obj_type1 and object_categories.get(str(obj1_id)) != obj_type1 and obj_type1 != "*": #added wildcard
            continue
        
        if obj_type2 and object_categories.get(str(obj2_id)) != obj_type2 and obj_type2 != "*": #added wildcard
            continue

        matching_relations.append(relation)

    return matching_relations

def query_json(json_data, image_id=None, relation_type=None, obj_type1=None, obj_type2=None):
    """Query the JSON data for matching images and relations."""
    matching_images = {}
    total_images = len(json_data)
    total_matches = 0
    
    for image in json_data:
        if image_id and image_id != "*" and str(image['image_id']) != image_id:
            print("Test filter", image_id)
            continue
        filtered_relations = filter_relations(image, relation_type, obj_type1, obj_type2)
        if filtered_relations:
            matching_images[image['image_id']] = filtered_relations
            total_matches += len(filtered_relations)
    
    print(f"{len(matching_images)} of {total_images} images matched query, found {total_matches} relations.")
    print("Matching Image IDs:", list(matching_images.keys()))
    return list(matching_images.keys())

def filter_annotations(json_file, new_name, image_ids, filter_type="positive", max_annotations=None):
    """
    Filters a JSON annotation file based on image IDs, filter type, and max annotations per image.
    
    :param json_file: Path to the annotation JSON file
    :param new_name: Name for the new filtered file
    :param image_ids: List or tuple of image IDs to filter
    :param filter_type: "positive" to keep only specified IDs, "negative" to exclude them
    :param max_annotations: Maximum number of annotations allowed per image (None for no limit)
    """
    # Load the JSON data
    with open(json_file, 'r') as f:
        data = json.load(f)
    
    # Determine filtering condition
    if filter_type == "positive":
        filtered_images = [img for img in data["images"] if img["id"] in image_ids]
        filtered_annotations = [ann for ann in data["annotations"] if ann["image_id"] in image_ids]
    elif filter_type == "negative":
        filtered_images = [img for img in data["images"] if img["id"] not in image_ids]
        filtered_annotations = [ann for ann in data["annotations"] if ann["image_id"] not in image_ids]
    else:
        raise ValueError("Invalid filter_type. Use 'positive' or 'negative'.")
    
    # Apply max_annotations filter
    if max_annotations is not None:
        annotation_counts = {}
        filtered_annotations = [
            ann for ann in filtered_annotations 
            if annotation_counts.setdefault(ann["image_id"], 0) < max_annotations and not annotation_counts.update({ann["image_id"]: annotation_counts[ann["image_id"]] + 1})
        ]
        valid_image_ids = {ann["image_id"] for ann in filtered_annotations}
        filtered_images = [img for img in filtered_images if img["id"] in valid_image_ids]
    
    # Create new JSON structure
    filtered_data = {
        "type": data["type"],
        "images": filtered_images,
        "annotations": filtered_annotations,
        "categories": data["categories"]  # Keep categories unchanged
    }
    
    # Define new filename
    new_filename = f"annotations_{new_name}_{filter_type}.json"
    
    # Save filtered JSON
    with open(new_filename, 'w') as f:
        json.dump(filtered_data, f, indent=4)
    
    print(f"Filtered JSON saved to {new_filename}")

def main():
    """Parse command-line arguments and execute the query."""
    file_path = "concept_data.json"  # Default file
    
    if len(sys.argv) > 1 and not sys.argv[1].isdigit() and sys.argv[1] != "*":
        file_path = sys.argv[1]
        args = sys.argv[2:]
    else:
        args = sys.argv[1:]
    
    image_id = args[0] if len(args) > 0 else "*"
    relation_type = args[1] if len(args) > 1 else None
    obj_type1 = args[2] if len(args) > 2 else None
    obj_type2 = args[3] if len(args) > 3 else None
    
    json_data = load_json(file_path)
    filter_list = query_json(json_data, image_id, relation_type, obj_type1, obj_type2)
    newname = 'filtered_by_' + relation_type

    #Custom dataset splits:
    filter_annotations('annotations.json', newname, filter_list, filter_type='positive', max_annotations=20)
    filter_annotations('annotations.json', newname, filter_list, filter_type='negative', max_annotations=20)

if __name__ == "__main__":
    main()

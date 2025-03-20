import json
from scipy.spatial.distance import euclidean
from itertools import combinations

def load_annotations(file_path):
    """Load the JSON annotation file."""
    with open(file_path, 'r') as f:
        data = json.load(f)
    return data

def save_concepts(file_path, concepts):
    """Save the detected concepts to a new JSON file."""
    with open(file_path, 'w') as f:
        json.dump(concepts, f, indent=4)

def filter_objects(annotations, categories):
    """Filter out objects labeled 'ignore' and return a dictionary by image_id."""
    ignore_category_id = {cat['id'] for cat in categories if cat['name'] == 'ignore'}
    objects_by_image = {}
    for obj in annotations:
        if obj['category_id'] not in ignore_category_id:
            objects_by_image.setdefault(obj['image_id'], []).append(obj)
    return objects_by_image

def sort_objects(objects, axis='x'):
    """Sort objects from left to right (x-axis) or top to bottom (y-axis)."""
    index = 0 if axis == 'x' else 1
    return sorted(objects, key=lambda obj: obj['bbox'][index])

def detect_relations(objects):
    """Detect positional, proximity, and overlap relations between objects."""
    relations = []
    sorted_objects_x = sort_objects(objects, 'x')
    sorted_objects_y = sort_objects(objects, 'y')
    
    for i, obj_A in enumerate(sorted_objects_x):
        for j in range(i + 1, len(sorted_objects_x)):
            obj_B = sorted_objects_x[j]
            relation = detect_left_right(obj_A, obj_B)
            if relation:
                relations.extend(relation)
    
    for i, obj_A in enumerate(sorted_objects_y):
        for j in range(i + 1, len(sorted_objects_y)):
            obj_B = sorted_objects_y[j]
            relation = detect_above_below(obj_A, obj_B)
            if relation:
                relations.extend(relation)
    
    relations.append(("left-to-right", *[obj['id'] for obj in sorted_objects_x]))
    relations.append(("top-to-bottom", *[obj['id'] for obj in sorted_objects_y]))
    
     # Flatten detected clusters
    for cluster in detect_clusters(objects):
        relations.append(("grouped", *cluster))

    # Flatten detected overlaps
    for overlap in detect_overlaps(objects):
        relations.append(("overlapping", *overlap))
    
    for depth_estimate in estimate_depth(objects):
        relations.append(depth_estimate)
	
    return relations

def detect_left_right(obj_A, obj_B):
    """Detect if one object is left or right of another."""
    x_min_A, _, w_A, _ = obj_A['bbox']
    x_max_A = x_min_A + w_A
    x_min_B, _, w_B, _ = obj_B['bbox']
    x_max_B = x_min_B + w_B
    rel = []
    if x_max_A < x_min_B:
        return [('left-of', obj_A['id'], obj_B['id']), ('right-of', obj_B['id'], obj_A['id'])]
    elif x_max_B < x_min_A:
        return [('right-of', obj_A['id'], obj_B['id']), ('left-of', obj_B['id'], obj_A['id'])]
    return None


def detect_above_below(obj_A, obj_B):
    """Detect if one object is above or below another."""
    _, y_min_A, _, h_A = obj_A['bbox']
    y_max_A = y_min_A + h_A
    _, y_min_B, _, h_B = obj_B['bbox']
    y_max_B = y_min_B + h_B
    
    if y_max_A < y_min_B:
        return [('above', obj_A['id'], obj_B['id']), ('below', obj_B['id'], obj_A['id'])]
    elif y_max_B < y_min_A:
        return [('below', obj_A['id'], obj_B['id']), ('above', obj_B['id'], obj_A['id'])]
    return None

def detect_clusters(objects):
    """Detect clusters of objects based on a dynamic proximity threshold."""
    clusters = []
    ungrouped_objects = set(obj['id'] for obj in objects)
    
    for obj_A, obj_B in combinations(objects, 2):
        size_A = max(obj_A['bbox'][2], obj_A['bbox'][3])
        size_B = max(obj_B['bbox'][2], obj_B['bbox'][3])
        dynamic_threshold = max(size_A, size_B) * 0.8  # 50% of larger object's size, 50% seems to restrictive, increase to 70%, try 80%
        
        center_A = (obj_A['bbox'][0] + obj_A['bbox'][2] / 2, obj_A['bbox'][1] + obj_A['bbox'][3] / 2)
        center_B = (obj_B['bbox'][0] + obj_B['bbox'][2] / 2, obj_B['bbox'][1] + obj_B['bbox'][3] / 2)
        
        if euclidean(center_A, center_B) < dynamic_threshold:
            found_cluster = None
            for cluster in clusters:
                if obj_A['id'] in cluster or obj_B['id'] in cluster:
                    cluster.update([obj_A['id'], obj_B['id']])
                    found_cluster = cluster
                    break
            
            if not found_cluster:
                clusters.append(set([obj_A['id'], obj_B['id']]))
            
            ungrouped_objects.discard(obj_A['id'])
            ungrouped_objects.discard(obj_B['id'])
    
    #clusters.extend([{obj_id} for obj_id in ungrouped_objects]) #we dont need single object clusters
    return [list(cluster) for cluster in clusters if len(cluster) > 1]

def detect_overlaps(objects):
    """Detect overlapping objects based on bounding box intersection."""
    overlaps = []
    for obj_A, obj_B in combinations(objects, 2):
        xA = max(obj_A['bbox'][0], obj_B['bbox'][0])
        yA = max(obj_A['bbox'][1], obj_B['bbox'][1])
        xB = min(obj_A['bbox'][0] + obj_A['bbox'][2], obj_B['bbox'][0] + obj_B['bbox'][2])
        yB = min(obj_A['bbox'][1] + obj_A['bbox'][3], obj_B['bbox'][1] + obj_B['bbox'][3])
        
        if xA < xB and yA < yB:
            overlaps.append((obj_A['id'], obj_B['id']))
    
    return overlaps

def estimate_depth(objects):
    """Estimate relative depth for objects of the same category based on size and position with variance allowance."""
    depth_relations = []
    for obj_A, obj_B in combinations(objects, 2):
        if obj_A['category_id'] == obj_B['category_id']:
            width_A, height_A = obj_A['bbox'][2], obj_A['bbox'][3]
            width_B, height_B = obj_B['bbox'][2], obj_B['bbox'][3]
            
            width_ratio = width_A / width_B if width_A > width_B else width_B / width_A
            height_ratio = height_A / height_B if height_A > height_B else height_B / height_A
            
            allowed_variance = 1.2  # 20% variance allowance (not all cars same size)
            
            if width_ratio > allowed_variance and height_ratio > allowed_variance: ##fixed wrong way around, we want to be BIGGER than the variance before detecting a depth relation
                if obj_A['bbox'][3] < obj_B['bbox'][3] and obj_A['bbox'][1] < obj_B['bbox'][1]: #fixed origin consideration to be top left corner
                    depth_relations.append(('probably-closer-than',obj_A['id'],  obj_B['id']))
                elif obj_B['bbox'][3] < obj_A['bbox'][3] and obj_B['bbox'][1] < obj_A['bbox'][1]: #fixed origin consideration to be top left corner
                    depth_relations.append(('probably-closer-than', obj_B['id'], obj_A['id']))
    return depth_relations

def process_annotations(file_path):
    """Main function to process the annotation file and return concept relations."""
    data = load_annotations(file_path)
    images = {img['id']: img for img in data['images']}
    categories = data['categories']
    objects_by_image = filter_objects(data['annotations'], categories)
    
    results = []
    for image_id, objects in objects_by_image.items():
        relations = detect_relations(objects)
        categories_connected = {obj['id']: obj['category_id'] for obj in objects}
        results.append({
            'image_id': image_id,
            'relations': relations,
            'categories': categories_connected
        })
    save_concepts("concept_labels.json", results)
    return results

# Example usage
#json_output = process_annotations("annotations.json")
# print(json_output)
print(process_annotations("annotations.json"))


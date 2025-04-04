import random
import json

def generate_bbox(maxsize):
    x1 = random.randint(0, maxsize[0] - 2)
    y1 = random.randint(0, maxsize[1] - 2)
    x2 = random.randint(x1 + 1, maxsize[0])
    y2 = random.randint(y1 + 1, maxsize[1])
    return [x1, y1, x2, y2]

def generate_samples_exists(maxsize, target_label, num_target_samples, num_non_target_samples, available_labels):
    samples = []

    for _ in range(num_target_samples):
        bboxes = []
        num_bboxes = 1#random.randint(1, 5)  # Random number of bounding boxes per sample
        for _ in range(num_bboxes):
            bbox = generate_bbox(maxsize)
            bbox.append(target_label)
            bboxes.append(bbox)
        samples.append({"input": bboxes, "output": True})

    for _ in range(num_non_target_samples):
        bboxes = []
        num_bboxes = 1#random.randint(1, 5)  # Random number of bounding boxes per sample
        for _ in range(num_bboxes):
            bbox = generate_bbox(maxsize)
            label = random.choice([label for label in available_labels if label != target_label])
            bbox.append(label)
            bboxes.append(bbox)
        samples.append({"input": bboxes, "output": False})

    return samples
    
def generate_samples_same_class(maxsize, available_labels, num_samples):
    samples = []
    minpositive = 10
    for i in range(num_samples):
        bboxes = []
        counterpos = minpositive
        label1 = random.choice(available_labels)
        label2 = random.choice(available_labels)
        if label1 == label2:
            counterpos = counterpos -1
        if counterpos > 0 and i >= 0.5*num_samples:
            counterpos = counterpos - 1
            label2 = label1
        

        bbox1 = generate_bbox(maxsize)
        bbox1.append(label1)
        bboxes.append(bbox1)

        bbox2 = generate_bbox(maxsize)
        bbox2.append(label2)
        bboxes.append(bbox2)

        output = (label1 == label2)
        samples.append({"input": bboxes, "output": output})

    return samples
    
def generate_samples_right_of(maxsize, available_labels, num_samples):
    samples = []
    minpositive = 10

    for i in range(num_samples):
        bboxes = []
        counterpos = minpositive
        label1 = random.choice(available_labels)
        label2 = random.choice(available_labels)
        if label1 == label2:
            counterpos = counterpos -1
        if counterpos > 0 and i >= 0.5*num_samples:
            counterpos = counterpos - 1
            label2 = label1

        bbox1 = generate_bbox(maxsize)
        bbox1.append(label1)
        bboxes.append(bbox1)

        bbox2 = generate_bbox(maxsize)
        bbox2.append(label2)
        bboxes.append(bbox2)

        # Check if bbox2 is clearly to the right of bbox1
        output = (label1 == label2) and (bbox2[0] > bbox1[2])
        samples.append({"input": bboxes, "output": output})

    return samples

# Parameters
maxsize = (20, 20)  # Maximum image size (width, height)
target_label = 5
num_target_samples = 10
num_non_target_samples = 20
available_labels = [1, 2, 3, 4, 5, 6, 7, 8, 9]
num_samples = 30

# Generate samples exists
samples = generate_samples_exists(maxsize, target_label, num_target_samples, num_non_target_samples, available_labels)
# Generate samples same label
samples = generate_samples_same_class(maxsize, available_labels, num_samples)
# Generate samples right of 
samples = generate_samples_right_of(maxsize, available_labels, num_samples)


# Save to JSON file
with open('synthetic_samples.json', 'w') as f:
    json.dump(samples, f, indent=4)

print("Synthetic samples generated and saved to 'synthetic_samples.json'.")


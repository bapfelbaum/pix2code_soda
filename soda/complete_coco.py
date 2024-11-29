import json 

#Load dataset
with open('instances.json', 'r') as f:
    data = json.load(f)

#update annon with iscrowd and segmentation
for annotations in data['annotations']:
    if 'iscrowd' not in annotation:
        annotation['iscrowd'] = 0 #default value
    if 'segmentation' not in annotation:
        annotation['segmentation'] = [] #default value
#
with open('instances.json','w') as f:
    json.dump(data, f)
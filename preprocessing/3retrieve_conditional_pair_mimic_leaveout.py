import argparse
import os
import os.path as osp
import json
import numpy as np
import pandas as pd
import scipy.spatial
from tqdm import tqdm

SUBSET = ['val', 'train', 'test']


def vector_distance(vec1, vec2, method = "l2", l2_normalize = True):
    """Computes the distance between 2 vectors
    Inspired by https://github.com/Azure/ImageSimilarityUsingCntk=
    Args:
        vec1: First vector between which the distance will be computed
        vec2: Second vector
        method: Type of distance to be computed, e.g. "l1" or "l2"
        l2_normalize: Flag indicating whether the vectors should be normalized
        to be of unit length before the distance between them is computed
    Returns: Distance between the 2 input vectors
    """
    # Pre-processing
    if l2_normalize:
        vec1 = vec1 / np.linalg.norm(vec1, 2)
        vec2 = vec2 / np.linalg.norm(vec2, 2)

    # Distance computation
    vecDiff = vec1 - vec2
    method = method.lower()
    if method == "l1":
        dist = sum(abs(vecDiff))
    elif method == "l2":
        dist = np.linalg.norm(vecDiff, 2)
    elif method == "normalizedl2":
        a = vec1 / np.linalg.norm(vec1, 2)
        b = vec2 / np.linalg.norm(vec2, 2)
        dist = np.linalg.norm(a - b, 2)
    elif method == "cosine":
        dist = scipy.spatial.distance.cosine(vec1, vec2)
    elif method == "correlation":
        dist = scipy.spatial.distance.correlation(vec1, vec2)
    elif method == "chisquared":
        dist = scipy.chiSquared(vec1, vec2)
    elif method == "normalizedchisquared":
        a = vec1 / sum(vec1)
        b = vec2 / sum(vec2)
        dist = scipy.chiSquared(a, b)
    elif method == "hamming":
        dist = scipy.spatial.distance.hamming(vec1 > 0, vec2 > 0)
    else:
        raise Exception("Distance method unknown: " + method)
    return dist


def load_leave_out_data():
    with open('/home/shuxinyang/data/mimic/finding/pair_list.json', 'r') as f:
        pair_list = json.load(f)
    new_pair_list = {'retrieve': {}, 'train': {}, 'val': {}, 'test': {}}
    for split in ['train', 'val', 'test']:
        print(len(pair_list[split]))
        for item in pair_list[split]:
            if split == 'train' and len(pair_list[split][item]) > 1:
                new_pair_list['retrieve'][item] = pair_list[split][item]
            else:
                new_pair_list[split][item] = pair_list[split][item]
    return new_pair_list


def get_simi(args, split_file, topk=10):
    npy_file = {}
    npy_file_norm = {}

    datas = load_leave_out_data()

    # load all data to memory
    file_split = {'train': [], 'val': [], 'test': [], 'retrieve': []}
    for subset in ['retrieve', 'train', 'val', 'test']:
        print("========>> precess {} set".format(subset))
        data = datas[subset]
        for subject_id in tqdm(data):
            studys = data[subject_id]
            for i, study in enumerate(studys):
                if i > 0:
                    continue
                patient_name = osp.basename(study['path'])[:-4]
                vec = np.load(osp.join(args.feature, patient_name + '.npy'))
                vec = np.mean(vec, axis=1)
                # normalized to be of unit length
                vec_norm = np.linalg.norm(vec, 2)
                npy_file[study['path']] = vec / vec_norm

                file_split[subset].append(study['path'])

    retrieve_lists = file_split['retrieve']
    print("Number of Retrieve Set : ", len(retrieve_lists))
    # prepare store top10 similar information by cosion distance
    simi_info = {"filename": [], 'split': [], 'method': []}
    for i in range(topk):
        simi_info["similar_{:d}".format(i)] = []
        simi_info["distance_{:d}".format(i)] = []

    for subset in SUBSET:
        print("========>> precess {} set".format(subset))
        file_lists = file_split[subset]
        for target in tqdm(file_lists):
            this_simi = []
            for pair_filename in retrieve_lists:
                if target == pair_filename:
                    continue

                # dist = vector_distance(npy_file[target], npy_file[pair_filename], args.method)
                # dist = scipy.spatial.distance.cosine(npy_file[target], npy_file[pair_filename])
                vec_t, vec_p = npy_file[target], npy_file[pair_filename]
                dist = 1 - np.dot(vec_t, vec_p)
                this_simi.append({"pair_filename": pair_filename, "similar_distance": dist})

            # store this image's top10 similar information
            this_simi = sorted(this_simi, key=lambda x: x["similar_distance"])
            simi_info['filename'].append(target)
            simi_info['split'].append(subset)
            simi_info['method'].append(args.method)
            for i, this_simi in enumerate(this_simi[:topk]):
                simi_info["similar_{:d}".format(i)].append(this_simi["pair_filename"])
                simi_info["distance_{:d}".format(i)].append(this_simi["similar_distance"])

    csv_filename = osp.join(args.output, 'leave_out_similar_pair_list.csv')
    csv_df = pd.DataFrame(simi_info)
    csv_df.to_csv(csv_filename, index=False)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('-d', '--root', type=str, default="/home/shuxinyang/data/mimic/finding",
                        help="the begin directory of all")
    parser.add_argument('-s', '--split', type=str, default="/home/shuxinyang/data/mimic/finding/leave_out_pair_list.json",
                        help="split file")
    parser.add_argument('-f', '--feature', type=str, default="/home/shuxinyang/data/mimic/features",
                        help="feature dir")
    parser.add_argument('-o', '--output', type=str, default="/home/shuxinyang/data/mimic/finding/",
                        help="output file save dir")
    parser.add_argument('-m', '--method', type=str, default="cosine",
                        help="similarity method")

    args = parser.parse_args()
    print(args)

    get_simi(args, args.split)
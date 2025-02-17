# '''
# 本文件用于从DeepSpeech特征中选择最佳帧作为固定嘴型的参考帧
# '''

# from tqdm import tqdm
# import numpy as np
# import shutil
# import os
# import glob

# # 基础路径设置
# base_path = '../asserts/training_data'
# deepspeech_path = f'{base_path}/split_video_25fps_deepspeech'
# crop_face_path = f'{base_path}/split_video_25fps_crop_face'

# # 目标logits字符和其索引的映射
# target_logits = {'p': 16, 's': 19, 'e': 5, 'f': 6, 'w': 23}

# # 读取DeepSpeech特征
# def read_deepspeech_features(txt_path):
#     with open(txt_path, 'r') as f:
#         lines = f.readlines()
#     features = np.array([np.fromstring(line, sep=' ') for line in lines])
#     return features

# # 处理单个数据集
# def process_dataset(txt_path, dataset_name):
#     features = read_deepspeech_features(txt_path)
#     best_frames = {char: {'max_logit': 0, 'frame_index': None} for char in target_logits}

#     # 遍历每一帧，找到每个字符对应的最大logit值
#     for i, frame_logits in enumerate(features):
#         char_index = np.argmax(frame_logits)
#         max_logit_value = frame_logits[char_index]
#         if char_index in target_logits.values():
#             logit_char = [char for char, index in target_logits.items() if index == char_index][0]
#             if max_logit_value > best_frames[logit_char]['max_logit']:
#                 best_frames[logit_char]['max_logit'] = max_logit_value
#                 best_frames[logit_char]['frame_index'] = i

#     # 保存置信度最高的帧对应的图像
#     for char, info in best_frames.items():
#         frame_index = info['frame_index']
#         if frame_index is not None:
#             # 定位图像文件
#             folder_index = frame_index // 9
#             image_name = f'{frame_index:06d}.jpg'
#             source_image_path = os.path.join(crop_face_path, dataset_name, f'{folder_index:06d}', image_name)
#             target_image_name = f'{char}.jpg'
#             target_image_path = os.path.join(crop_face_path, dataset_name, target_image_name)
            
#             if os.path.exists(source_image_path):
#                 shutil.copy(source_image_path, target_image_path)
#             else:
#                 print(f'Warning: {source_image_path} not exists!')

# # 遍历deepspeech文件夹处理所有数据集, 保存固定嘴型的最佳帧
# if __name__ == '__main__':
#     txt_files = glob.glob(f'{deepspeech_path}/*.txt')
#     for txt_file in tqdm(txt_files, desc='Overall Progress'):
#         dataset_name = os.path.basename(txt_file).replace('_deepspeech.txt', '')
#         process_dataset(txt_file, dataset_name)


'''
本文件用于从DeepSpeech特征中选择置信度最高的前五帧作为固定嘴型的参考帧，并在文件名后加上_1, _2, _3, _4, _5以区分不同帧。
'''

from tqdm import tqdm
import numpy as np
import shutil
import os
import glob

# 基础路径设置
base_path = '../asserts/training_data'
deepspeech_path = f'{base_path}/split_video_25fps_deepspeech'
crop_face_path = f'{base_path}/split_video_25fps_crop_face'

# 目标logits字符和其索引的映射
target_logits = {'p': 16, 's': 19, 'e': 5, 'f': 6, 'w': 23}

# 读取DeepSpeech特征
def read_deepspeech_features(txt_path):
    with open(txt_path, 'r') as f:
        lines = f.readlines()
    features = np.array([np.fromstring(line, sep=' ') for line in lines])
    return features

# 处理单个数据集
def process_dataset(txt_path, dataset_name, num_frames=10):
    features = read_deepspeech_features(txt_path)
    best_frames = {char: {'max_logits': [], 'frame_indices': []} for char in target_logits}

    # 遍历每一帧，找到每个字符对应的最大logit值，并记录前五帧
    for i, frame_logits in enumerate(features):
        char_index = np.argmax(frame_logits)
        max_logit_value = frame_logits[char_index]
        if char_index in target_logits.values():
            logit_char = [char for char, index in target_logits.items() if index == char_index][0]
            # 将当前帧的logit值和索引添加到列表中
            best_frames[logit_char]['max_logits'].append(max_logit_value)
            best_frames[logit_char]['frame_indices'].append(i)
    
    # 对每个字符的帧进行排序，选择置信度最高的前十个帧
    for char in target_logits:
        if best_frames[char]['max_logits']:
            best_frames[char]['max_logits'], best_frames[char]['frame_indices'] = zip(*sorted(zip(best_frames[char]['max_logits'], best_frames[char]['frame_indices']), reverse=True))
            best_frames[char]['frame_indices'] = best_frames[char]['frame_indices'][:num_frames]  # 取前十个索引

    # 保存置信度最高的前十个帧对应的图像
    for char, info in best_frames.items():
        for index, frame_index in enumerate(info['frame_indices']):
            if frame_index is not None:
                # 定位图像文件
                folder_index = frame_index // 9
                image_name = f'{frame_index:06d}.jpg'
                source_image_path = os.path.join(crop_face_path, dataset_name, f'{folder_index:06d}', image_name)
                suffix = f'_{index + 1}'  # 文件名后缀，从1开始
                target_image_name = f'{char}{suffix}.jpg'
                target_image_path = os.path.join(crop_face_path, dataset_name, target_image_name)
                
                if os.path.exists(source_image_path):
                    shutil.copy(source_image_path, target_image_path)
                else:
                    print(f'Warning: {source_image_path} not exists!', "char:", char, "index:", index)

# 遍历deepspeech文件夹处理所有数据集, 保存固定嘴型的最佳帧
if __name__ == '__main__':
    # selected frames number
    num_frames = 20

    txt_files = glob.glob(f'{deepspeech_path}/*.txt')
    for txt_file in tqdm(txt_files, desc='Overall Progress'):
        dataset_name = os.path.basename(txt_file).replace('_deepspeech.txt', '')
        process_dataset(txt_file, dataset_name, num_frames)
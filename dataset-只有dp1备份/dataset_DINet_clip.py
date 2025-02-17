import torch
import numpy as np
import json
import random
import cv2
import os
from torch.utils.data import Dataset
from tqdm import tqdm
from pathlib import Path

# 导入自定义模块和方法
# from models.Gaussian_blur import Gaussian_bluring
# from utils.data_processing import load_landmark_openface_origin
# from tensor_processing import SmoothMask

# 预处理和数据加载函数
def load_selected_reference_frames(folder_path, img_h=416, img_w=320):
    """
    在给定的文件夹路径中随机选取以'p', 's', 'e', 'f', 'w'开头的jpg文件各一张，
    读取它们为参考帧，并返回处理后的参考帧列表。
    
    :param folder_path: 文件夹路径，其中包含以特定字符开头的jpg图像文件。
    :param img_h: 目标图像高度
    :param img_w: 目标图像宽度
    :return: 包含处理后的参考帧数据的列表。
    """
    reference_frame_list = []
    target_chars = ['p', 's', 'e', 'f', 'w']
    
    for char in target_chars:
        # 在文件夹中找到所有以当前字符开头的jpg文件
        char_files = list(Path(folder_path).glob(f'{char}*.jpg'))
        if char_files:
            # 从符合条件的文件中随机选择一个
            selected_file = random.choice(char_files)
            # 读取并处理图像
            reference_frame_data = cv2.imread(str(selected_file))[:, :, ::-1] / 255.0
            if reference_frame_data.shape != (img_h, img_w, 3):
                reference_frame_data = cv2.resize(reference_frame_data, (img_w, img_h))
            reference_frame_list.append(reference_frame_data)
        else:
            print(f'No file found for character {char} in folder {folder_path}')
            return []
    
    return reference_frame_list # 5个参考帧的list, 每个参考帧的shape为(416, 320, 3)

def get_data(json_name,augment_num):
    """
    从指定的JSON文件中加载数据，并根据增强次数扩展数据集。
    
    :param json_name: JSON文件名，包含数据集的详细信息。
    :param augment_num: 数据增强的次数。
    :return: 数据集的名称列表和数据字典。
    """
    print('start loading data from json file...', json_name)
    with open(json_name,'r') as f:
        data_dic = json.load(f)
    data_dic_name_list = []
    for augment_index in tqdm(range(augment_num)):  # Wrapped with tqdm for progress tracking
        for video_name in data_dic.keys():
            data_dic_name_list.append(video_name)
    random.shuffle(data_dic_name_list)
    print('finish loading')
    return data_dic_name_list,data_dic

def display_concatenated_images_and_save(source_clip_list, reference_clip_list, save_path):
    # Concatenate source clips and their masks horizontally
    display_source = np.concatenate(source_clip_list, 1)
    # display_source_mask = np.concatenate(source_clip_mask_list, 1)

    # Concatenate reference clips horizontally for each reference
    display_references = [np.concatenate([reference_clip_list[i][:, :, j:j+3] for j in range(0, 15, 3)], 1) for i in range(len(reference_clip_list))]

    # Concatenate everything vertically
    merge_img = np.concatenate([display_source] + display_references, 0)

    # Save the image
    cv2.imwrite(save_path, (merge_img[:,:,::-1] * 255).astype(np.uint8))

# 数据集类定义
class DINetDataset(Dataset):
    def __init__(self, path_json, augment_num, mouth_region_size):
        """
        初始化DINet数据集。
        
        :param path_json: 包含训练数据信息的JSON文件路径。
        :param augment_num: 数据增强次数。
        :param mouth_region_size: 嘴部区域的大小。
        """
        self.path_json = path_json
        self.augment_num = augment_num
        self.mouth_region_size = mouth_region_size
        self.data_dic_name_list, self.data_dic = get_data(path_json, augment_num)
        self.img_h = mouth_region_size * 3 // 2 + mouth_region_size // 8
        self.img_w = mouth_region_size + mouth_region_size // 4
        # self.smoothmask = SmoothMask()
        # self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.selected_reference_frame = False


    def __getitem__(self, index):
        """
        根据索引获取数据集中的单个项。
        
        :param index: 数据项的索引。
        :return: 一个包含多个元素的元组，这些元素分别是：
                 - source_clip：源视频片段。
                 - source_clip_mask：应用掩码后的源视频片段。
                 - reference_clip：参考视频片段。
                 - deep_speech_clip：对应的深度语音特征。
                 - deep_speech_full：完整的深度语音特征。
                 - flag：标志位，指示数据是否有效。
        """
        flag = torch.ones(1)
        video_name = self.data_dic_name_list[index]
        video_clip_num = len(self.data_dic[video_name]['clip_data_list'])

        if video_clip_num < 6:
            # 如果视频片段数量小于6，则认为是脏数据，返回零样本
            print("视频片段数量小于6，则认为是脏数据，返回零样本 video_path:",video_name)
            return self.zero_sample_with_batch()

        source_clip_list, reference_clip_list, deep_speech_list, reference_for_dV = [], [], [], []

        # 随机选择一个源视频片段作为锚点
        source_anchor = random.sample(range(video_clip_num), 1)[0]

        for frame_index in range(2, 7):  # 一次加载5帧
            try:
                source_frame_path = self.data_dic[video_name]['clip_data_list'][source_anchor]['frame_path_list'][frame_index]
                source_frame = self.preprocess_image_data(source_frame_path)
                source_clip_list.append(source_frame)
                # source_clip_mask_list.append(source_frame)  # 假定mask处理相同
                
                # 加载深度语音特征
                deep_speech_array = np.array(self.data_dic[video_name]['clip_data_list'][source_anchor]['deep_speech_list'][frame_index - 2:frame_index + 3])
                deep_speech_list.append(deep_speech_array)

            except IndexError or KeyError:
                # 数据索引出错，返回零样本
                return self.zero_sample_with_batch()

        # 验证加载的数据有效性
        if not self.check_data_validity(deep_speech_list, (5, 29)):
            print("deep_speech_list 数据无效, path:",video_name)
            print("source anchor:",source_anchor)
            return self.zero_sample_with_batch()

        # 如果使用固定口型参考帧
        if self.selected_reference_frame:
            for _ in range(5):
                reference_frame_list = load_selected_reference_frames( 
                            f'./asserts/training_data/split_video_25fps_crop_face/{video_name}', self.img_h, self.img_w) # 5个参考帧的list, 每个参考帧的shape为(h, w, 3)
                if len(reference_frame_list) < 5:
                    # 如果参考帧数量不足5张，数据不完整，返回零样本
                    print("固定口型的参考帧数量不足5张，数据不完整，返回零样本")
                    return self.zero_sample_with_batch()
                # 拼接参考帧
                reference_clip_list.append(np.concatenate(reference_frame_list, axis=2))  # 沿RGB通道拼接
        else:
            # 加载随机参考帧
            reference_clip_list = self.load_reference_clips(video_name, video_clip_num)

        source_clip = np.stack(source_clip_list, 0) # source_clip shape: (5, 468, 360, 3)
        deep_speech_full = np.array(self.data_dic[video_name]['clip_data_list'][source_anchor]['deep_speech_list']) # deep_speech_full shape: (9, 29)
        deep_speech_clip = np.stack(deep_speech_list, 0) # deep_speech_clip shape: (5, 5, 29)
        reference_clip = np.stack(reference_clip_list, 0) # reference_clip shape: (5, 468, 360, 15)

        # import pdb; pdb.set_trace()
        # print("source_clip shape:",source_clip.shape)
        # print("deep_speech_clip shape:",deep_speech_clip.shape)
        # print("deep_speech_full shape:",deep_speech_full.shape)
        # print("reference_clip shape:",reference_clip.shape)

        # # 验证加载的数据有效性
        # display_concatenated_images_and_save(source_clip_list, reference_clip_list, f'./check_data_{int(flag.cpu())}.jpg')
        # ## 暂停 等待输入
        # input("Press Enter to continue...")

        source_clip = torch.from_numpy(source_clip).float().permute(0, 3, 1, 2) # source_clip shape: (5, 3, 468, 360)
        reference_clip = torch.from_numpy(reference_clip).float().permute(0, 3, 1, 2) # reference_clip shape: (5, 15, 468, 360)
        deep_speech_clip = torch.from_numpy(deep_speech_clip).float().permute(0, 2, 1) # deep_speech_clip shape: (5, 29, 5)
        deep_speech_full = torch.from_numpy(deep_speech_full).permute(1, 0) # deep_speech_full shape: (29, 9)

        return source_clip, reference_clip, deep_speech_clip, deep_speech_full, flag

    def __len__(self):
        # 返回数据集大小
        return len(self.data_dic_name_list)

    def zero_sample_with_batch(self):
        """
        当数据有误时，返回零样本，不是随机样本，包括批处理情况。
        """
        shape = (5, 3, self.img_h, self.img_w)  # 假定批大小为5，通道数为3
        source_clip = torch.zeros(shape)
        reference_clip = torch.zeros((5, 15, self.img_h, self.img_w))  # 假定参考帧拼接后通道数为15
        deep_speech_clip = torch.zeros((5, 29, 5))  # 假定深度语音特征维度
        deep_speech_full = torch.zeros((29, 9))
        flag = torch.zeros(1)
        return source_clip, reference_clip, deep_speech_clip, deep_speech_full, flag

    def preprocess_image_data(self, image_path):
        """
        预处理图像数据。
        
        :param image_path: 图像文件的路径。
        :return: 预处理后的图像数据。
        """
        image_data = cv2.imread(image_path)[:, :, ::-1] / 255.0  # 读取图像并转换为RGB
        if image_data.shape != (self.img_h, self.img_w, 3):
            image_data = cv2.resize(image_data, (self.img_w, self.img_h))  # 调整图像尺寸
        return image_data
    
    def load_reference_clips(self, video_name, video_clip_num):
        """
        加载参考视频片段。
        """
        reference_clip_list = []

        for _ in range(5):  # 假设需要5个source_image, 每个source_image有5个参考帧
            reference_anchor_list = random.sample(range(video_clip_num), 5)
            reference_frame_list = []

            for reference_anchor in reference_anchor_list:
                reference_frame_path_list = self.data_dic[video_name]['clip_data_list'][reference_anchor]['frame_path_list']
                # 如果文件夹内的帧数量不足9张，数据不完整，返回零样本
                if len(reference_frame_path_list) < 9:
                    return self.zero_sample_with_batch()

                reference_random_index = random.sample(range(9), 1)[0]
                reference_frame_path = reference_frame_path_list[reference_random_index]

                # 如果参考帧文件不存在，返回零样本
                if not os.path.isfile(reference_frame_path):
                    return self.zero_sample_with_batch()

                reference_frame_data = self.preprocess_image_data(reference_frame_path)
                reference_frame_list.append(reference_frame_data) # 5个参考帧的list, 每个参考帧的shape为(468, 360, 3)

            # 验证参考帧数据有效性
            if not self.check_data_validity(reference_frame_list, (self.img_h, self.img_w, 3)):
                print("参考帧数据无效, path:",video_name)
                return self.zero_sample_with_batch()

            # import pdb; pdb.set_trace()
            reference_clip_list.append(np.concatenate(reference_frame_list, axis=2))  # 沿宽度方向拼接
            
        return reference_clip_list # 5个source_image的参考帧的list, 每个source_image参考帧的shape为(468, 360, 15)

    def check_data_validity(self, data_list, expected_shape):
        """
        检查数据有效性。
        
        :param data_list: 待检查的数据列表。
        :param expected_shape: 期望的数据形状。
        :return: 数据是否有效的布尔值。
        """
        # 如果送入的是list
        if isinstance(data_list, list):
            for data in data_list:
                # print("type data",type(data))
                if not isinstance(data, np.ndarray):
                    print("数据类型不是ndarray")
                    return False
                if not np.array_equal(data.shape, expected_shape):
                    print("数据形状不符合期望：", data.shape, "期望：", expected_shape)
                    return False  # 数据无效
            return True  # 数据有效
        else:
            # deepspeech_feature_tensor
            if not np.array_equal(data_list.shape, expected_shape):
                print("数据形状不符合期望：", data_list.shape, "期望：", expected_shape)
                return False
            return False


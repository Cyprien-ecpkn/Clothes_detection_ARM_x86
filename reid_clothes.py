#!/usr/bin/python3
# -*- coding: utf-8 -*-
# @Time : 2021/1/18 下午6:02
# @Author : zengwb

import os
import cv2
import torch
import warnings
import argparse
import numpy as np
import onnxruntime as ort
from utils.datasets import LoadStreams, LoadImages
from utils.draw import draw_boxes
from utils.general import check_img_size
from utils.torch_utils import time_synchronized
from person_detect_yolov5 import Person_detect
from deep_sort import build_tracker
from utils.parser import get_config
from utils.log import get_logger
from utils.torch_utils import select_device, load_classifier, time_synchronized
# count
from collections import Counter
from collections import deque
import math
from PIL import Image, ImageDraw, ImageFont

def tlbr_midpoint(box):
    minX, minY, maxX, maxY = box
    midpoint = (int((minX + maxX) / 2), int((minY + maxY) / 2))  # minus y coordinates to get proper xy format
    return midpoint


def intersect(A, B, C, D):
    return ccw(A, C, D) != ccw(B, C, D) and ccw(A, B, C) != ccw(A, B, D)


def ccw(A, B, C):
    return (C[1] - A[1]) * (B[0] - A[0]) > (B[1] - A[1]) * (C[0] - A[0])


def vector_angle(midpoint, previous_midpoint):
    x = midpoint[0] - previous_midpoint[0]
    y = midpoint[1] - previous_midpoint[1]
    return math.degrees(math.atan2(y, x))


def get_size_with_pil(label,size=25):
    font = ImageFont.truetype("./configs/simkai.ttf", size, encoding="utf-8")  # simhei.ttf
    return font.getsize(label)


#为了支持中文，用pil
def put_text_to_cv2_img_with_pil(cv2_img,label,pt,color):
    pil_img = cv2.cvtColor(cv2_img, cv2.COLOR_BGR2RGB)  # cv2和PIL中颜色的hex码的储存顺序不同，需转RGB模式
    pilimg = Image.fromarray(pil_img)  # Image.fromarray()将数组类型转成图片格式，与np.array()相反
    draw = ImageDraw.Draw(pilimg)  # PIL图片上打印汉字
    font = ImageFont.truetype("./configs/simkai.ttf", 25, encoding="utf-8") #simhei.ttf
    draw.text(pt, label, color,font=font)
    return cv2.cvtColor(np.array(pilimg), cv2.COLOR_RGB2BGR)  # 将图片转成cv2.imshow()可以显示的数组格式


colors = np.array([
    [1,0,1],
    [0,0,1],
    [0,1,1],
    [0,1,0],
    [1,1,0],
    [1,0,0]
    ]);

def get_color(c, x, max):
    ratio = (x / max) * 5;
    i = math.floor(ratio);
    j = math.ceil(ratio);
    ratio -= i;
    r = (1 - ratio) * colors[i][c] + ratio * colors[j][c];
    return r;

def compute_color_for_labels(class_id,class_total=80):
    offset = (class_id + 0) * 123457 % class_total;
    red = get_color(2, offset, class_total);
    green = get_color(1, offset, class_total);
    blue = get_color(0, offset, class_total);
    return (int(red*256),int(green*256),int(blue*256))

# special add
clo_label_path = "clo_yolo/obj.names"
clo_weightsPath = "clo_yolo/obj_4000.weights"
clo_configPath = "clo_yolo/obj.cfg"

def get_person_img(img, bbox):
    for i, box in enumerate(bbox):
        x1, y1, x2, y2 = [int(i) for i in box]
        # box text and bar
        print("x_y is : ", end='')
        print(img.shape)
        print(x1)
        print(x2)
        print(y1)
        print(y2)
        cv2.imwrite("./temp_person_img/{}.png".format(i), img[y1:y2, x1:x2, :])

def clo_load_label(label_path):
    label = []
    classesFile1 = label_path
    with open(classesFile1, 'rt') as f:
        label = f.read().rstrip('\n').split('\n')

    return label

def clo_color_init(Labels):
    np.random.seed(42)
    COLORS = np.random.randint(0, 255, size=(len(Labels), 3), dtype="uint8")

    return COLORS

def clo_net_init(cfg_path, weight_path):
    net1 = cv2.dnn.readNetFromDarknet(cfg_path, weight_path)
    net1.setPreferableBackend(cv2.dnn.DNN_BACKEND_OPENCV)
    net1.setPreferableTarget(cv2.dnn.DNN_TARGET_CPU)

    return net1

def deal_exist_id(id, id_day, id_cloth, id_confidences1, id_classid, now_id):
    new_id_day = []
    new_id_cloth = []
    new_id_confidences1 = []
    new_id_classid = []
    for i in range(len(now_id)):
        new_id_day.append(1)
        new_id_cloth.append([-1, -1, -1, -1])
        new_id_confidences1.append([0])
        new_id_classid.append([0])
        if now_id[i] in id:
            for j in range(len(id)):
                if now_id[i] == id[j]:
                    new_id_day[i] = id_day[j] + 1
                    new_id_cloth[i] = id_cloth[j]
                    new_id_confidences1[i] = id_confidences1[j]
                    new_id_classid[i] = id_classid[j]
                    break

    return now_id, new_id_day, new_id_cloth, new_id_confidences1, new_id_classid


class yolo_reid():
    def __init__(self, cfg, args, path):
        self.logger = get_logger("root")
        self.args = args
        self.video_path = path
        use_cuda = args.use_cuda and torch.cuda.is_available()
        if not use_cuda:
            warnings.warn("Running in cpu mode which maybe very slow!", UserWarning)

        self.person_detect = Person_detect(self.args, self.video_path)
        imgsz = check_img_size(args.img_size, s=32)  # self.model.stride.max())  # check img_size
        self.dataset = LoadImages(self.video_path, img_size=imgsz)
        self.deepsort = build_tracker(cfg, args.sort, use_cuda=use_cuda)
        self.img_cnt = 0

        # about the clothes detection
        self.clo_net1 = clo_net_init(clo_configPath, clo_weightsPath)
        self.clo_Labels = clo_load_label(clo_label_path)
        self.clo_COLORS = clo_color_init(self.clo_Labels)


    def deep_sort(self):
        idx_frame = 0
        results = []
        paths = {}
        track_cls = 0
        last_track_id = -1
        total_track = 0
        angle = -1
        total_counter = 0
        up_count = 0
        down_count = 0
        class_counter = Counter()   # store counts of each detected class
        already_counted = deque(maxlen=50)   # temporary memory for storing counted IDs

        # 在这里需要开始维护一个数组，这个数组里面记录的是每个ID上一帧所包含的 存在信息 以及 服装信息
        exist_id = []
        exist_id_day = []
        exist_id_clo = []
        exist_id_confidences1 = []
        exist_id_classid = []

        temp_path, vid_writer = None, None
        fourcc='mp4v'
        save_path = './output.mp4'
        for video_path, img, ori_img, vid_cap in self.dataset:
            idx_frame += 1
            # print('aaaaaaaa', video_path, img.shape, im0s.shape, vid_cap)
            t1 = time_synchronized()

            # yolo detection
            bbox_xywh, cls_conf, cls_ids, xy = self.person_detect.detect(video_path, img, ori_img, vid_cap)

            # do tracking
            outputs = self.deepsort.update(bbox_xywh, cls_conf, ori_img)

            # 1.视频中间画行黄线
            line = [(0, int(0.48 * ori_img.shape[0])), (int(ori_img.shape[1]), int(0.48 * ori_img.shape[0]))]
            # cv2.line(ori_img, line[0], line[1], (0, 255, 255), 4)

            # 2. 统计人数
            for track in outputs:
                bbox = track[:4]
                track_id = track[-1]
                midpoint = tlbr_midpoint(bbox)

                origin_midpoint = (midpoint[0], ori_img.shape[0] - midpoint[1])  # get midpoint respective to botton-left

                if track_id not in paths:
                    paths[track_id] = deque(maxlen=2)
                    total_track = track_id
                paths[track_id].append(midpoint)
                previous_midpoint = paths[track_id][0]
                origin_previous_midpoint = (previous_midpoint[0], ori_img.shape[0] - previous_midpoint[1])

                if intersect(midpoint, previous_midpoint, line[0], line[1]) and track_id not in already_counted:
                    class_counter[track_cls] += 1
                    total_counter += 1
                    # last_track_id = track_id;
                    # draw red line
                    # cv2.line(ori_img, line[0], line[1], (0, 0, 255), 10)

                    already_counted.append(track_id)  # Set already counted for ID to true.

                    angle = vector_angle(origin_midpoint, origin_previous_midpoint)

                    if angle > 0:
                        up_count += 1
                    if angle < 0:
                        down_count += 1

                if len(paths) > 50:
                    del paths[list(paths)[0]]

            # 3. 绘制人员
            if len(outputs) > 0:
                bbox_tlwh = []
                bbox_xyxy = outputs[:, :4]
                identities = outputs[:, -1]

                # add to test
                # get_person_img(ori_img, bbox_xyxy)

                # identities is ID array
                ori_img = draw_boxes(ori_img, bbox_xyxy, identities)

                # add clothes detection part
                id_location = 0
                exist_id, exist_id_day, exist_id_clo, exist_id_confidences1, exist_id_classid = deal_exist_id(exist_id, exist_id_day, exist_id_clo, exist_id_confidences1, exist_id_classid, identities)

                for i, box in enumerate(bbox_xyxy):
                    # clothes detection's person's id
                    clo_id = int(identities[id_location]) if identities is not None else 0
                    id_location += 1
                    # print("clo_id is : ", end="")
                    # print(clo_id)

                    x1, y1, x2, y2 = [int(i) for i in box]
                    clo_img = ori_img[y1:y2, x1:x2, :]
                    (H, W) = clo_img.shape[:2]

                    ln = self.clo_net1.getLayerNames()
                    ln = [ln[i - 1] for i in self.clo_net1.getUnconnectedOutLayers()]
                    blob1 = cv2.dnn.blobFromImage(clo_img, 1 / 255.0, (416, 416), swapRB=True, crop=False)
                    self.clo_net1.setInput(blob1)
                    layerOutputs = self.clo_net1.forward(ln)

                    boxes1 = []
                    confidences1 = []
                    classIDs1 = []

                    find_flag = False
                    for output in layerOutputs:
                        for detection in output:

                            scores = detection[5:]
                            classID = np.argmax(scores)
                            confidence = scores[classID]

                            if confidence > 0.5:
                                find_flag = True
                                box = detection[0:4] * np.array([W, H, W, H])
                                # box_location
                                (centerX, centerY, width, height) = box.astype("int")
                                clo_x = int(centerX - (width / 2))
                                clo_y = int(centerY - (height / 2))
                                boxes1.append([clo_x, clo_y, int(width), int(height)])

                                # confidence and classDI information
                                confidences1.append(float(confidence))
                                classIDs1.append(classID)

                    if find_flag:
                        exist_id_clo[id_location-1] = boxes1
                        exist_id_confidences1[id_location-1] = confidences1
                        exist_id_classid[id_location-1] = classIDs1
                    else:
                        if exist_id_clo[id_location-1][0] != -1:
                            boxes1 = exist_id_clo[id_location-1]
                            confidences1 = exist_id_confidences1[id_location-1]
                            classIDs1 = exist_id_classid[id_location-1]
                    # print("Flag : ", end="")
                    # print(find_flag)
                    # print(exist_id)
                    # print(exist_id_day)
                    # print(exist_id_clo)

                    idxs = cv2.dnn.NMSBoxes(boxes1, confidences1, 0.5, 0.1)

                    if len(idxs) > 0:
                        # print("detected!")
                        for i in idxs.flatten():
                            (clo_x, clo_y) = (boxes1[i][0] + x1, boxes1[i][1] + y1)
                            (w, h) = (boxes1[i][2], boxes1[i][3])

                            color = [int(c) for c in self.clo_COLORS[classIDs1[i]]]

                            cv2.rectangle(ori_img, (clo_x, clo_y), (clo_x + w, clo_y + h), color, 3)
                            texts = "{}: {:.4f}".format(self.clo_Labels[classIDs1[i]], confidences1[i])
                            cv2.putText(ori_img, texts, (clo_x, clo_y - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.75, color, 3)

                for bb_xyxy in bbox_xyxy:
                    bbox_tlwh.append(self.deepsort._xyxy_to_tlwh(bb_xyxy))

            print("yolo+deepsort:", time_synchronized() - t1)

            # 4. 绘制统计信息
            # label = "total num: {}".format(str(total_track))
            # t_size = get_size_with_pil(label, 25)
            # x1 = 20
            # y1 = 50
            # color = compute_color_for_labels(2)
            # cv2.rectangle(ori_img, (x1 - 1, y1), (x1 + t_size[0] + 10, y1 - t_size[1]), color, 2)
            # ori_img = put_text_to_cv2_img_with_pil(ori_img, label, (x1 + 5, y1 - t_size[1] - 2), (0, 0, 0))

            # label = "穿过黄线人数: {} ({} 向上, {} 向下)".format(str(total_counter), str(up_count), str(down_count))
            # t_size = get_size_with_pil(label, 25)
            # x1 = 20
            # y1 = 100
            # color = compute_color_for_labels(2)
            # cv2.rectangle(ori_img, (x1 - 1, y1), (x1 + t_size[0] + 10, y1 - t_size[1]), color, 2)
            # ori_img = put_text_to_cv2_img_with_pil(ori_img, label, (x1 + 5, y1 - t_size[1] - 2), (0, 0, 0))

            # if last_track_id >= 0:
            #     label = "最新: 行人{}号{}穿过黄线".format(str(last_track_id), str("向上") if angle >= 0 else str('向下'))
            #     t_size = get_size_with_pil(label, 25)
            #     x1 = 20
            #     y1 = 150
            #     color = compute_color_for_labels(2)
            #     cv2.rectangle(ori_img, (x1 - 1, y1), (x1 + t_size[0] + 10, y1 - t_size[1]), color, 2)
            #     ori_img = put_text_to_cv2_img_with_pil(ori_img, label, (x1 + 5, y1 - t_size[1] - 2), (255, 0, 0))

            end = time_synchronized()

            if self.args.display:
                # cv2.imshow("test", ori_img)
                cv2.imwrite("./temp_img/{}.jpg".format(self.img_cnt), ori_img)
                print(self.img_cnt)
                self.img_cnt += 1
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break
            if temp_path != save_path:  # new video
                temp_path = save_path
                if isinstance(vid_writer, cv2.VideoWriter):
                    vid_writer.release()  # release previous video writer
    
                fps = vid_cap.get(cv2.CAP_PROP_FPS)
                width = int(vid_cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                height = int(vid_cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                vid_writer = cv2.VideoWriter(save_path, cv2.VideoWriter_fourcc(*fourcc), fps, (width, height))
            vid_writer.write(ori_img)

            self.logger.info("{}/time: {:.03f}s, fps: {:.03f}, detection numbers: {}, tracking numbers: {}" \
                             .format(idx_frame, end - t1, 1 / (end - t1),
                                     bbox_xywh.shape[0], len(outputs)))

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--video_path", default='./new_input_0.mp4', type=str)
    parser.add_argument("--camera", action="store", dest="cam", type=int, default="-1")
    parser.add_argument('--device', default='cuda:0', help='cuda device, i.e. 0 or 0,1,2,3 or cpu')
    # yolov5
    parser.add_argument('--weights', nargs='+', type=str, default='./weights/yolov5s.pt', help='model.pt path(s)')
    parser.add_argument('--img-size', type=int, default=960, help='inference size (pixels)')
    parser.add_argument('--conf-thres', type=float, default=0.4, help='object confidence threshold')
    parser.add_argument('--iou-thres', type=float, default=0.5, help='IOU threshold for NMS')
    parser.add_argument('--classes', default=[0], type=int, help='filter by class: --class 0, or --class 0 2 3')
    parser.add_argument('--agnostic-nms', action='store_true', help='class-agnostic NMS')
    parser.add_argument('--augment', action='store_true', help='augmented inference')

    # deep_sort
    parser.add_argument("--sort", default=True, help='True: sort model, False: reid model')
    parser.add_argument("--config_deepsort", type=str, default="./configs/deep_sort.yaml")
    parser.add_argument("--display", default=True, help='show resule')
    parser.add_argument("--frame_interval", type=int, default=1)
    parser.add_argument("--cpu", dest="use_cuda", action="store_false", default=True)

    return parser.parse_args()


if __name__ == '__main__':
    args = parse_args()
    cfg = get_config()
    cfg.merge_from_file(args.config_deepsort)

    yolo_reid = yolo_reid(cfg, args, path=args.video_path)
    with torch.no_grad():
        yolo_reid.deep_sort()

import cv2
import numpy as np
import onnxruntime as ort
import os

class SCRFD:
    def __init__(self, model_file, nms_thresh=0.4, det_thresh=0.5, input_size=(640, 640)):
        self.model_file = model_file
        self.session = ort.InferenceSession(self.model_file, providers=['CPUExecutionProvider'])
        self.center_cache = {}
        self.nms_thresh = nms_thresh
        self.det_thresh = det_thresh
        self.input_size = input_size
        self._init_vars()

    def _init_vars(self):
        input_cfg = self.session.get_inputs()[0]
        input_shape = input_cfg.shape
        # Input shape typically: [1, 3, 640, 640]
        if isinstance(input_shape[2], str):
            self.input_height = None
            self.input_width = None
        else:
            self.input_height = input_shape[2]
            self.input_width = input_shape[3]
        
        self.input_name = input_cfg.name
        self.output_names = [o.name for o in self.session.get_outputs()]
        
        # SCRFD strides for "det_500m" (buffalo_s) are usually [8, 16, 32]
        self.fmc = 3
        self._feat_stride_fpn = [8, 16, 32]
        self._num_anchors = 2
        self.use_kps = True

    def prepare(self, ctx_id, **kwargs):
        # Placeholder for compatibility if needed, but we do everything in init
        pass

    def forward(self, img, threshold):
        scores_list = []
        bboxes_list = []
        kpss_list = []
        input_size = tuple(img.shape[0:2][::-1])
        
        # Blob preparation
        blob = cv2.dnn.blobFromImage(img, 1.0/128, input_size, (127.5, 127.5, 127.5), swapRB=True)
        
        net_outs = self.session.run(self.output_names, {self.input_name: blob})

        input_height = blob.shape[2]
        input_width = blob.shape[3]

        fmc = self.fmc
        for idx, stride in enumerate(self._feat_stride_fpn):
            scores = net_outs[idx]
            bbox_preds = net_outs[idx + fmc]
            bbox_preds = bbox_preds * stride
            
            if self.use_kps:
                kps_preds = net_outs[idx + fmc * 2] * stride

            height = input_height // stride
            width = input_width // stride
            K = height * width
            key = (height, width, stride)

            if key in self.center_cache:
                anchor_centers = self.center_cache[key]
            else:
                anchor_centers = np.stack(np.mgrid[:height, :width][::-1], axis=-1).astype(np.float32)
                anchor_centers = (anchor_centers * stride).reshape( (-1, 2) )
                if self._num_anchors>1:
                    anchor_centers = np.stack([anchor_centers]*self._num_anchors, axis=1).reshape( (-1,2) )
                if len(self.center_cache)<100:
                    self.center_cache[key] = anchor_centers

            pos_inds = np.where(scores>=threshold)[0]
            bboxes = distance2bbox(anchor_centers, bbox_preds)
            pos_scores = scores[pos_inds]
            pos_bboxes = bboxes[pos_inds]
            scores_list.append(pos_scores)
            bboxes_list.append(pos_bboxes)
            
            if self.use_kps:
                kpss = distance2kps(anchor_centers, kps_preds)
                kpss = kpss.reshape( (kpss.shape[0], -1, 2) )
                pos_kpss = kpss[pos_inds]
                kpss_list.append(pos_kpss)

        return scores_list, bboxes_list, kpss_list

    def detect(self, img, input_size=None, max_num=0, metric='default'):
        if input_size is None:
            input_size = self.input_size
            
        im_ratio = float(img.shape[0]) / img.shape[1]
        model_ratio = float(input_size[1]) / input_size[0]
        
        if im_ratio > model_ratio:
            new_height = input_size[1]
            new_width = int(new_height / im_ratio)
        else:
            new_width = input_size[0]
            new_height = int(new_width * im_ratio)
            
        det_scale = float(new_height) / img.shape[0]
        resized_img = cv2.resize(img, (new_width, new_height))
        
        det_img = np.zeros( (input_size[1], input_size[0], 3), dtype=np.uint8 )
        det_img[:new_height, :new_width, :] = resized_img

        scores_list, bboxes_list, kpss_list = self.forward(det_img, self.det_thresh)

        scores = np.vstack(scores_list)
        scores_ravel = scores.ravel()
        order = scores_ravel.argsort()[::-1]
        
        bboxes = np.vstack(bboxes_list) / det_scale
        
        if self.use_kps:
            kpss = np.vstack(kpss_list) / det_scale
            
        pre_det = np.hstack((bboxes, scores)).astype(np.float32, copy=False)
        pre_det = pre_det[order, :]
        keep = self.nms(pre_det)
        det = pre_det[keep, :]
        
        if self.use_kps:
            kpss = kpss[order,:,:]
            kpss = kpss[keep,:,:]
        else:
            kpss = None

        if max_num > 0 and det.shape[0] > max_num:
            area = (det[:, 2] - det[:, 0]) * (det[:, 3] - det[:, 1])
            img_center = img.shape[0] // 2, img.shape[1] // 2
            offsets = np.vstack([
                (det[:, 0] + det[:, 2]) / 2 - img_center[1],
                (det[:, 1] + det[:, 3]) / 2 - img_center[0]
            ])
            offset_dist_squared = np.sum(np.power(offsets, 2.0), 0)
            if metric == 'max':
                values = area
            else:
                values = area - offset_dist_squared * 2.0  # some extra weight on center
            bindex = np.argsort(values)[::-1]
            bindex = bindex[0:max_num]
            det = det[bindex, :]
            if kpss is not None:
                kpss = kpss[bindex, :]

        return det, kpss

    def nms(self, dets):
        thresh = self.nms_thresh
        x1 = dets[:, 0]
        y1 = dets[:, 1]
        x2 = dets[:, 2]
        y2 = dets[:, 3]
        scores = dets[:, 4]

        areas = (x2 - x1 + 1) * (y2 - y1 + 1)
        order = scores.argsort()[::-1]

        keep = []
        while order.size > 0:
            i = order[0]
            keep.append(i)
            xx1 = np.maximum(x1[i], x1[order[1:]])
            yy1 = np.maximum(y1[i], y1[order[1:]])
            xx2 = np.minimum(x2[i], x2[order[1:]])
            yy2 = np.minimum(y2[i], y2[order[1:]])

            w = np.maximum(0.0, xx2 - xx1 + 1)
            h = np.maximum(0.0, yy2 - yy1 + 1)
            inter = w * h
            ovr = inter / (areas[i] + areas[order[1:]] - inter)

            inds = np.where(ovr <= thresh)[0]
            order = order[inds + 1]

        return keep

def distance2bbox(points, distance, max_shape=None):
    x1 = points[:, 0] - distance[:, 0]
    y1 = points[:, 1] - distance[:, 1]
    x2 = points[:, 0] + distance[:, 2]
    y2 = points[:, 1] + distance[:, 3]
    if max_shape is not None:
        x1 = np.clip(x1, 0, max_shape[1])
        y1 = np.clip(y1, 0, max_shape[0])
        x2 = np.clip(x2, 0, max_shape[1])
        y2 = np.clip(y2, 0, max_shape[0])
    return np.stack([x1, y1, x2, y2], axis=-1)

def distance2kps(points, distance, max_shape=None):
    """Convert anchor-relative distances to absolute keypoint coordinates."""
    preds = []
    for i in range(0, distance.shape[1], 2):
        # Explicit column references: 0 = x anchor, 1 = y anchor
        px = points[:, 0] + distance[:, i]
        py = points[:, 1] + distance[:, i + 1]
        if max_shape is not None:
            px = np.clip(px, 0, max_shape[1])
            py = np.clip(py, 0, max_shape[0])
        preds.append(px)
        preds.append(py)
    return np.stack(preds, axis=-1)

class Landmark106:
    def __init__(self, model_file):
        self.model_file = model_file
        self.session = ort.InferenceSession(self.model_file, providers=['CPUExecutionProvider'])
        self.input_name = self.session.get_inputs()[0].name
        self.input_shape = self.session.get_inputs()[0].shape # [1, 3, 192, 192]
        self.input_size = (192, 192)

    def get(self, img, face_bbox):
        w, h = face_bbox[2] - face_bbox[0], face_bbox[3] - face_bbox[1]
        center = (face_bbox[0] + w*0.5, face_bbox[1] + h*0.5)
        _scale = 192.0 / (max(w, h)*1.5)
        
        # Matrix construction to map center to (96, 96)
        # x_new = scale * (x - cx) + 96
        tx = 96.0 - _scale * center[0]
        ty = 96.0 - _scale * center[1]
        
        M = np.array([
            [_scale, 0, tx],
            [0, _scale, ty]
        ], dtype=np.float32)
        
        blob = cv2.warpAffine(img, M, (192, 192), borderValue=0.0)
        blob = cv2.dnn.blobFromImage(blob, 1.0, (192, 192), (0,0,0), swapRB=True)
        
        pred = self.session.run(None, {self.input_name: blob})[0]
        pred = pred.reshape((-1, 2))
        
        # De-normalize: model output is [-1, 1], map to [0, 192]
        pred = (pred + 1.0) * 96.0
        
        # Transform back to original image coordinates
        IM = cv2.invertAffineTransform(M)
        pred_homo = np.hstack((pred, np.ones((pred.shape[0], 1))))
        original_points = np.dot(pred_homo, IM.T)
        
        return original_points.astype(np.float32)

class Face:
    def __init__(self, bbox, kps, lms106=None, det_score=0.0):
        self.bbox = bbox # [x1, y1, x2, y2]
        self.kps = kps   # 5 keypoints
        self.landmark_2d_106 = lms106
        self.det_score = det_score


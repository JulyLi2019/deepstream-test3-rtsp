#!/usr/bin/env python3

################################################################################
# Copyright (c) 2020, NVIDIA CORPORATION. All rights reserved.
#
# Permission is hereby granted, free of charge, to any person obtaining a
# copy of this software and associated documentation files (the "Software"),
# to deal in the Software without restriction, including without limitation
# the rights to use, copy, modify, merge, publish, distribute, sublicense,
# and/or sell copies of the Software, and to permit persons to whom the
# Software is furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.  IN NO EVENT SHALL
# THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
# FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
# DEALINGS IN THE SOFTWARE.
################################################################################
import argparse
import sys

sys.path.append('../')
import gi
import configparser

gi.require_version('Gst', '1.0')
gi.require_version('GstRtspServer', '1.0')
from gi.repository import GObject, Gst, GstRtspServer
from gi.repository import GLib
from ctypes import *
import time
import sys
import math
import platform
from common.is_aarch_64 import is_aarch64
from common.bus_call import bus_call
from common.FPS import GETFPS

import pyds
import pyds_bbox_meta

fps_streams = {}

MAX_DISPLAY_LEN = 64
PGIE_CLASS_ID_VEHICLE = 0
PGIE_CLASS_ID_BICYCLE = 1
PGIE_CLASS_ID_PERSON = 2
PGIE_CLASS_ID_ROADSIGN = 3
MUXER_OUTPUT_WIDTH = 1920
MUXER_OUTPUT_HEIGHT = 1080
MUXER_BATCH_TIMEOUT_USEC = 4000000
TILED_OUTPUT_WIDTH = 1280
TILED_OUTPUT_HEIGHT = 720
GST_CAPS_FEATURES_NVMM = "memory:NVMM"
OSD_PROCESS_MODE = 0
OSD_DISPLAY_TEXT = 1
frame_number = 0
pgie_classes_str = ["Vehicle", "TwoWheeler", "Person", "RoadSign"]

out_counts = 0
in_counts = 0
Front_frame_det_number = 0
boat_Front_chuanti_queding = []
# codec = "H264"


def xywh2xyxy(x, y, w, h):
    x1 = x - (w / 2)
    y1 = y - (h / 2)
    x2 = x + (w / 2)
    y2 = y + (h / 2)
    return [x1, y1, x2, y2]


def IOU(A, B):
    W = min(A[2], B[2]) - max(A[0], B[0])
    H = min(A[3], B[3]) - max(A[1], B[1])
    if W <= 0 or H <= 0:
        return 0
    SA = (A[2] - A[0]) * (A[3] - A[1])
    SB = (B[2] - B[0]) * (B[3] - B[1])
    cross = W * H
    return cross / (SA + SB - cross)


# tiler_sink_pad_buffer_probe  will extract metadata received on OSD sink pad
# and update params for drawing rectangle, object information etc.
def tiler_src_pad_buffer_probe(pad, info, u_data):
    # frame_number = 0
    # num_rects = 0
    # linshi_data=[]
    # 记录前框的数组
    global boat_Front_chuanti_queding
    # 初始化进出进出船数量
    global out_counts
    global in_counts
    # 记录前一帧中检测框的数量
    global Front_frame_det_number
    # det_boxe_number = 0

    # 从管道中获取推理结果
    gst_buffer = info.get_buffer()
    if not gst_buffer:
        print("Unable to get GstBuffer ")
        return

    # Retrieve batch metadata from the gst_buffer
    # Note that pyds.gst_buffer_get_nvds_batch_meta() expects the
    # C address of gst_buffer as input, which is obtained with hash(gst_buffer)
    batch_meta = pyds.gst_buffer_get_nvds_batch_meta(hash(gst_buffer))
    l_frame = batch_meta.frame_meta_list
    while l_frame is not None:
        try:
            # Note that l_frame.data needs a cast to pyds.NvDsFrameMeta
            # The casting is done by pyds.NvDsFrameMeta.cast()
            # The casting also keeps ownership of the underlying memory
            # in the C code, so the Python garbage collector will leave
            # it alone.
            frame_meta = pyds.NvDsFrameMeta.cast(l_frame.data)



        except StopIteration:
            break

        '''
        print("Frame Number is ", frame_meta.frame_num)
        print("Source id is ", frame_meta.source_id)
        print("Batch id is ", frame_meta.batch_id)
        print("Source Frame Width ", frame_meta.source_frame_width)
        print("Source Frame Height ", frame_meta.source_frame_height)
        print("Num object meta ", frame_meta.num_obj_meta)
        '''


        frame_number = frame_meta.frame_num
        l_obj = frame_meta.obj_meta_list
        num_rects = frame_meta.num_obj_meta
        # obj_counter = {
        #     PGIE_CLASS_ID_VEHICLE: 0,
        #     PGIE_CLASS_ID_PERSON: 0,
        #     PGIE_CLASS_ID_BICYCLE: 0,
        #     PGIE_CLASS_ID_ROADSIGN: 0
        # }

        # 获取帧图像尺寸,并且设置计数线位置
        x_coord = frame_meta.source_frame_width
        y_coord = frame_meta.source_frame_height
        jishu_line = int(x_coord / 4)
        Front_det_boxes = []
        det_boxe_number = 0

        if frame_number == 0: #判断是不是第一帧
        # 获取图片帧里面的检测框并进行处理
            while l_obj is not None:
                try:
                    # Casting l_obj.data to pyds.NvDsObjectMeta
                    # obj_meta = pyds.NvDsObjectMeta.cast(l_obj.data)
                    obj_meta = pyds_bbox_meta.NvDsObjectMeta.cast(l_obj.data)

                    if obj_meta.class_id == 0:

                        boxInfo = obj_meta.detector_bbox_info
                        box_Coord = boxInfo.org_bbox_coords

                        left = box_Coord.left
                        top = box_Coord.top
                        width = box_Coord.width
                        height = box_Coord.height

                        # left = obj_meta.detector_bbox_info.org_bbox_coords.left
                        # top = obj_meta.detector_bbox_info.org_bbox_coords.top
                        # width = obj_meta.detector_bbox_info.org_bbox_coords.width
                        # height = obj_meta.detector_bbox_info.org_bbox_coords.height

                        det_boxe = xywh2xyxy(left, top, width, height)

                        x = (det_boxe[0] + det_boxe[2]) / 2
                        y = (det_boxe[1] + det_boxe[3]) / 2

                        if x < jishu_line:
                            ss = [det_boxe[0], det_boxe[1], det_boxe[2], det_boxe[3], 0, x, y]  # 代表向右
                        else:
                            ss = [det_boxe[0], det_boxe[1], det_boxe[2], det_boxe[3], 1, x, y]  # 代表向左
                        # 此处和C代码部分有点差别
                        Front_det_boxes.append(ss)
                        # print("Front_det_boxes:", Front_det_boxes)
                        # print("det_boxe_number", det_boxe_number)
                        det_boxe_number = det_boxe_number + 1


                except StopIteration:
                    break
                # obj_counter[obj_meta.class_id] += 1
                try:
                    l_obj = l_obj.next
                except StopIteration:
                    break
        else:
            # 获取图片帧里面的检测框并进行处理
            while l_obj is not None:

                # 获取坐标信息
                # obj_meta = pyds.NvDsObjectMeta.cast(l_obj.data)
                obj_meta = pyds_bbox_meta.NvDsObjectMeta.cast(l_obj.data)
                if obj_meta.class_id == 0:
                    boxInfo = obj_meta.detector_bbox_info
                    box_Coord = boxInfo.org_bbox_coords
                    left = box_Coord.left
                    top = box_Coord.top
                    width = box_Coord.width
                    height = box_Coord.height

                    # left = obj_meta.detector_bbox_info.org_bbox_coords.left
                    # top = obj_meta.detector_bbox_info.org_bbox_coords.top
                    # width = obj_meta.detector_bbox_info.org_bbox_coords.width
                    # height = obj_meta.detector_bbox_info.org_bbox_coords.height


                    det_boxe = xywh2xyxy(left, top, width, height)

                    hh=0 #用于判断是不是新蹦出来的目标

                    # for i in range(Front_frame_det_number):
                    #     Front_det_boxe_xy = boat_Front_chuanti_queding[i]
                    for Front_det_boxe_xy in boat_Front_chuanti_queding:
                        if IOU(det_boxe,Front_det_boxe_xy) > 0.5:
                            Front_det_boxe_xy[0:4] = det_boxe
                            hh = 1
                            # 加入中心点的坐标，且防止局部往回走
                            # 获取框的中心点坐标
                            x = (det_boxe[2] + det_boxe[0]) / 2
                            y = (det_boxe[3] + det_boxe[1]) / 2
                            if Front_det_boxe_xy[4] == 0:  # 向右走
                                if Front_det_boxe_xy[-2] > x:
                                    Front_det_boxe_xy.append(Front_det_boxe_xy[-2])
                                    Front_det_boxe_xy.append(Front_det_boxe_xy[-2])
                                else:
                                    Front_det_boxe_xy.append(x)
                                    Front_det_boxe_xy.append(y)
                            else:
                                if Front_det_boxe_xy[-2] < x:
                                    Front_det_boxe_xy.append(Front_det_boxe_xy[-2])
                                    Front_det_boxe_xy.append(Front_det_boxe_xy[-2])
                                else:
                                    Front_det_boxe_xy.append(x)
                                    Front_det_boxe_xy.append(y)
                            # --------------------------------------------------------------------------------------------#
                            Front_det_boxes.append(Front_det_boxe_xy)
                            # print("Front_det_boxes:", Front_det_boxes)
                            # print("det_boxe_number", det_boxe_number)
                            det_boxe_number = det_boxe_number+1

                    if hh==0:
                        # 当前框有，前框没有
                        # -------------------------------------------------------------------------------------------------#
                        # 用于船舶计数
                        x = (det_boxe[2] + det_boxe[0]) / 2
                        y = (det_boxe[3] + det_boxe[1]) / 2
                        if x < jishu_line:  # 记录方向
                            ss = [det_boxe[0], det_boxe[1], det_boxe[2], det_boxe[3], 0, x, y]  # 这个是向右方走
                        else:
                            ss = [det_boxe[0], det_boxe[1], det_boxe[2], det_boxe[3], 1, x, y]  # 这个是向左方走
                        Front_det_boxes.append(ss)
                        # print("Front_det_boxes:", Front_det_boxes)
                        # print("det_boxe_number", det_boxe_number)
                        det_boxe_number = det_boxe_number+1

                l_obj = l_obj.next







        Front_frame_det_number=det_boxe_number
        boat_Front_chuanti_queding = Front_det_boxes
        # 船舶计数
        for boat_counts_frame in boat_Front_chuanti_queding:
            if len(boat_counts_frame) >= 9:
                center_x1 = boat_counts_frame[-2]
                center_y1 = boat_counts_frame[-1]
                center_x2 = boat_counts_frame[-4]
                center_y2 = boat_counts_frame[-3]

                # 进入的船舶数
                if center_x1 > jishu_line and center_x2 <= jishu_line:
                    in_counts = in_counts + 1
                # 出去的船舶数
                if center_x1 < jishu_line and center_x2 >= jishu_line:
                    out_counts = out_counts + 1

        #画左上角的统计信息
        display_meta = pyds.nvds_acquire_display_meta_from_pool(batch_meta)
        display_meta.num_labels = 1
        py_nvosd_text_params = display_meta.text_params[0]
        py_nvosd_text_params.display_text = "in_count={} out_count={}".format(in_counts, out_counts)
        py_nvosd_text_params.x_offset = 30
        py_nvosd_text_params.y_offset = 30
        py_nvosd_text_params.font_params.font_name = "Serif"
        py_nvosd_text_params.font_params.font_size = 30
        py_nvosd_text_params.font_params.font_color.red = 1.0
        py_nvosd_text_params.font_params.font_color.green = 1.0
        py_nvosd_text_params.font_params.font_color.blue = 1.0
        py_nvosd_text_params.font_params.font_color.alpha = 1.0
        py_nvosd_text_params.set_bg_clr = 1
        py_nvosd_text_params.text_bg_clr.red = 0.0
        py_nvosd_text_params.text_bg_clr.green = 0.0
        py_nvosd_text_params.text_bg_clr.blue = 0.0
        py_nvosd_text_params.text_bg_clr.alpha = 1.0
        # print("Frame Number=", frame_number, "Number of Objects=",num_rects,"Vehicle_count=",vehicle_count,"Person_count=",person)
        # pyds.nvds_add_display_meta_to_frame(frame_meta, display_meta)



        print("Frame Number=", frame_number, "in_counts=",
              in_counts, "out_counts=", out_counts)

        # 画线
        line_params = display_meta.line_params[0]
        display_meta.num_lines = 1
        line_params.line_width = 5
        line_params.line_color.set(0, 1, 0, 1)
        line_params.x1 = jishu_line
        line_params.y1 = 0
        line_params.x2 = jishu_line
        line_params.y2 = y_coord
        # Get frame rate through this probe
        pyds.nvds_add_display_meta_to_frame(frame_meta, display_meta)
        # fps_streams["stream{0}".format(frame_meta.pad_index)].get_fps()
        try:
            l_frame = l_frame.next
        except StopIteration:
            break
    return Gst.PadProbeReturn.OK


def cb_newpad(decodebin, decoder_src_pad, data):
    print("In cb_newpad\n")
    caps = decoder_src_pad.get_current_caps()
    gststruct = caps.get_structure(0)
    gstname = gststruct.get_name()
    source_bin = data
    features = caps.get_features(0)

    # Need to check if the pad created by the decodebin is for video and not
    # audio.
    print("gstname=", gstname)
    if (gstname.find("video") != -1):
        # Link the decodebin pad only if decodebin has picked nvidia
        # decoder plugin nvdec_*. We do this by checking if the pad caps contain
        # NVMM memory features.
        print("features=", features)
        if features.contains("memory:NVMM"):
            # Get the source bin ghost pad
            bin_ghost_pad = source_bin.get_static_pad("src")
            if not bin_ghost_pad.set_target(decoder_src_pad):
                sys.stderr.write("Failed to link decoder src pad to source bin ghost pad\n")
        else:
            sys.stderr.write(" Error: Decodebin did not pick nvidia decoder plugin.\n")


def decodebin_child_added(child_proxy, Object, name, user_data):
    print("Decodebin child added:", name, "\n")
    if (name.find("decodebin") != -1):
        Object.connect("child-added", decodebin_child_added, user_data)


def create_source_bin(index, uri):
    print("Creating source bin")

    # Create a source GstBin to abstract this bin's content from the rest of the
    # pipeline
    bin_name = "source-bin-%02d" % index
    print(bin_name)
    nbin = Gst.Bin.new(bin_name)
    if not nbin:
        sys.stderr.write(" Unable to create source bin \n")

    # Source element for reading from the uri.
    # We will use decodebin and let it figure out the container format of the
    # stream and the codec and plug the appropriate demux and decode plugins.
    uri_decode_bin = Gst.ElementFactory.make("uridecodebin", "uri-decode-bin")
    if not uri_decode_bin:
        sys.stderr.write(" Unable to create uri decode bin \n")
    # We set the input uri to the source element
    uri_decode_bin.set_property("uri", uri)
    # Connect to the "pad-added" signal of the decodebin which generates a
    # callback once a new pad for raw data has beed created by the decodebin
    uri_decode_bin.connect("pad-added", cb_newpad, nbin)
    uri_decode_bin.connect("child-added", decodebin_child_added, nbin)

    # We need to create a ghost pad for the source bin which will act as a proxy
    # for the video decoder src pad. The ghost pad will not have a target right
    # now. Once the decode bin creates the video decoder and generates the
    # cb_newpad callback, we will set the ghost pad target to the video decoder
    # src pad.
    Gst.Bin.add(nbin, uri_decode_bin)
    bin_pad = nbin.add_pad(Gst.GhostPad.new_no_target("src", Gst.PadDirection.SRC))
    if not bin_pad:
        sys.stderr.write(" Failed to add ghost pad in source bin \n")
        return None
    return nbin


def main(args):
    # Check input arguments
    if len(args) < 2:
        sys.stderr.write("usage: %s <uri1> [uri2] ... [uriN]\n" % args[0])
        sys.exit(1)

    for i in range(0, len(args) - 1):
        fps_streams["stream{0}".format(i)] = GETFPS(i)
    number_sources = len(args) - 1

    # Standard GStreamer initialization
    GObject.threads_init()
    Gst.init(None)

    # Create gstreamer elements */
    # Create Pipeline element that will form a connection of other elements
    print("Creating Pipeline \n ")
    pipeline = Gst.Pipeline()
    is_live = False

    if not pipeline:
        sys.stderr.write(" Unable to create Pipeline \n")
    print("Creating streamux \n ")

    # Create nvstreammux instance to form batches from one or more sources.
    streammux = Gst.ElementFactory.make("nvstreammux", "Stream-muxer")
    if not streammux:
        sys.stderr.write(" Unable to create NvStreamMux \n")

    pipeline.add(streammux)
    for i in range(number_sources):
        print("Creating source_bin ", i, " \n ")
        uri_name = args[i + 1]
        if uri_name.find("rtsp://") == 0:
            is_live = True
        source_bin = create_source_bin(i, uri_name)
        if not source_bin:
            sys.stderr.write("Unable to create source bin \n")
        pipeline.add(source_bin)
        padname = "sink_%u" % i
        sinkpad = streammux.get_request_pad(padname)
        if not sinkpad:
            sys.stderr.write("Unable to create sink pad bin \n")
        srcpad = source_bin.get_static_pad("src")
        if not srcpad:
            sys.stderr.write("Unable to create src pad bin \n")
        srcpad.link(sinkpad)
    queue1 = Gst.ElementFactory.make("queue", "queue1")
    queue2 = Gst.ElementFactory.make("queue", "queue2")
    queue3 = Gst.ElementFactory.make("queue", "queue3")
    queue4 = Gst.ElementFactory.make("queue", "queue4")
    queue5 = Gst.ElementFactory.make("queue", "queue5")
    pipeline.add(queue1)
    pipeline.add(queue2)
    pipeline.add(queue3)
    pipeline.add(queue4)
    pipeline.add(queue5)
    print("Creating Pgie \n ")
    pgie = Gst.ElementFactory.make("nvinfer", "primary-inference")
    if not pgie:
        sys.stderr.write(" Unable to create pgie \n")
    print("Creating tiler \n ")
    tiler = Gst.ElementFactory.make("nvmultistreamtiler", "nvtiler")
    if not tiler:
        sys.stderr.write(" Unable to create tiler \n")
    print("Creating nvvidconv \n ")
    nvvidconv = Gst.ElementFactory.make("nvvideoconvert", "convertor")
    if not nvvidconv:
        sys.stderr.write(" Unable to create nvvidconv \n")
    print("Creating nvosd \n ")
    nvosd = Gst.ElementFactory.make("nvdsosd", "onscreendisplay")
    if not nvosd:
        sys.stderr.write(" Unable to create nvosd \n")
    nvosd.set_property('process-mode', OSD_PROCESS_MODE)
    nvosd.set_property('display-text', OSD_DISPLAY_TEXT)

    # transform = Gst.ElementFactory.make("nvegltransform", "nvegl-transform")
    # if not transform:
    #     sys.stderr.write(" Unable to create transform \n")

    nvvidconv_postosd = Gst.ElementFactory.make("nvvideoconvert", "convertor_postosd")
    if not nvvidconv_postosd:
        sys.stderr.write(" Unable to create nvvidconv_postosd \n")

    # Create a caps filter
    caps = Gst.ElementFactory.make("capsfilter", "filter")
    caps.set_property("caps", Gst.Caps.from_string("video/x-raw(memory:NVMM), format=I420"))

    # Make the encoder

    encoder = Gst.ElementFactory.make("nvv4l2h264enc", "encoder")
    print("Creating H264 Encoder")

    if not encoder:
        sys.stderr.write(" Unable to create encoder")
    # encoder.set_property('bitrate', bitrate)
    if is_aarch64():
        encoder.set_property('preset-level', 1)
        encoder.set_property('insert-sps-pps', 1)
        encoder.set_property('bufapi-version', 1)

    # Make the payload-encode video into RTP packets

    rtppay = Gst.ElementFactory.make("rtph264pay", "rtppay")

    if not rtppay:
        sys.stderr.write(" Unable to create rtppay")

    # Make the UDP sink
    updsink_port_num = 5400
    sink = Gst.ElementFactory.make("udpsink", "udpsink")
    if not sink:
        sys.stderr.write(" Unable to create udpsink")

    sink.set_property('host', '224.224.255.255')
    sink.set_property('port', updsink_port_num)
    sink.set_property('async', False)
    sink.set_property('sync', 1)

    # print("Playing file %s " % stream_path)
    # source.set_property('location', stream_path)

    if is_live:
        print("Atleast one of the sources is live")
        streammux.set_property('live-source', 1)

    streammux.set_property('width', 1920)
    streammux.set_property('height', 1080)
    streammux.set_property('batch-size', number_sources)
    streammux.set_property('batched-push-timeout', 4000000)
    #pgie.set_property('config-file-path', "dstest3_pgie_config.txt")
    pgie.set_property('config-file-path', "config_infer_primary_yoloV5.txt")
    pgie_batch_size = pgie.get_property("batch-size")
    if (pgie_batch_size != number_sources):
        print("WARNING: Overriding infer-config batch-size", pgie_batch_size, " with number of sources ",
              number_sources, " \n")
        pgie.set_property("batch-size", number_sources)
    tiler_rows = int(math.sqrt(number_sources))
    tiler_columns = int(math.ceil((1.0 * number_sources) / tiler_rows))
    tiler.set_property("rows", tiler_rows)
    tiler.set_property("columns", tiler_columns)
    tiler.set_property("width", TILED_OUTPUT_WIDTH)
    tiler.set_property("height", TILED_OUTPUT_HEIGHT)
    sink.set_property("qos", 0)

    print("Adding elements to Pipeline \n")
    pipeline.add(pgie)
    pipeline.add(tiler)
    pipeline.add(nvvidconv)
    pipeline.add(nvosd)
    # pipeline.add(transform)
    pipeline.add(nvvidconv_postosd)
    pipeline.add(caps)
    pipeline.add(encoder)
    pipeline.add(rtppay)
    pipeline.add(sink)

    print("Linking elements in the Pipeline \n")
    streammux.link(queue1)
    queue1.link(pgie)
    pgie.link(queue2)
    queue2.link(tiler)
    tiler.link(queue3)
    queue3.link(nvvidconv)
    nvvidconv.link(queue4)
    queue4.link(nvosd)
    if is_aarch64():
        nvosd.link(queue5)
        queue5.link(nvvidconv_postosd)
        # transform.link(nvvidconv_postosd)
        nvvidconv_postosd.link(caps)
        caps.link(encoder)
        encoder.link(rtppay)
        rtppay.link(sink)

    else:
        nvosd.link(queue5)
        queue5.link(sink)

        # create an event loop and feed gstreamer bus mesages to it
    loop = GObject.MainLoop()
    bus = pipeline.get_bus()
    bus.add_signal_watch()
    bus.connect("message", bus_call, loop)
    tiler_src_pad = pgie.get_static_pad("src")
    if not tiler_src_pad:
        sys.stderr.write(" Unable to get src pad \n")
    else:
        tiler_src_pad.add_probe(Gst.PadProbeType.BUFFER, tiler_src_pad_buffer_probe, 0)

    # Start streaming
    rtsp_port_num = 8554

    server = GstRtspServer.RTSPServer.new()
    server.props.service = "%d" % rtsp_port_num
    server.attach(None)

    factory = GstRtspServer.RTSPMediaFactory.new()
    factory.set_launch(
        "( udpsrc name=pay0 port=%d buffer-size=524288 caps=\"application/x-rtp, media=video, clock-rate=90000, encoding-name=(string)%s, payload=96 \" )" % (
        updsink_port_num, "H264"))
    factory.set_shared(True)
    server.get_mount_points().add_factory("/ds-test", factory)

    print("\n *** DeepStream: Launched RTSP Streaming at rtsp://localhost:%d/ds-test ***\n\n" % rtsp_port_num)

    # osdsinkpad = nvosd.get_static_pad("sink")
    # if not osdsinkpad:
    #     sys.stderr.write(" Unable to get sink pad of nvosd \n")

    # osdsinkpad.add_probe(Gst.PadProbeType.BUFFER, osd_sink_pad_buffer_probe, 0)
    # osdsinkpad.add_probe(Gst.PadProbeType.BUFFER, tiler_src_pad_buffer_probe, 0)

    # List the sources
    print("Now playing...")
    for i, source in enumerate(args):
        if (i != 0):
            print(i, ": ", source)

    print("Starting pipeline \n")
    # start play back and listed to events		
    pipeline.set_state(Gst.State.PLAYING)
    try:
        loop.run()
    except:
        pass
    # cleanup
    print("Exiting app\n")
    pipeline.set_state(Gst.State.NULL)

# def parse_args():
#     parser = argparse.ArgumentParser(description='RTSP Output Sample Application Help ')
#     parser.add_argument("-i", "--input",
#                   help="Path to input H264 elementry stream", required=True)
#     parser.add_argument("-c", "--codec", default="H264",
#                   help="RTSP Streaming Codec H264/H265 , default=H264", choices=['H264','H265'])
#     parser.add_argument("-b", "--bitrate", default=4000000,
#                   help="Set the encoding bitrate ", type=int)
#     # Check input arguments
#     if len(sys.argv)==1:
#         parser.print_help(sys.stderr)
#         sys.exit(1)
#     args = parser.parse_args()
#     global codec
#     global bitrate
#     global stream_path
#     codec = args.codec
#     bitrate = args.bitrate
#     stream_path = args.input
#     return 0

if __name__ == '__main__':
    # global codec
    sys.exit(main(sys.argv))

import os
import sys
import math
import moviepy.editor as mpy
from time import sleep
from powerShell import runWithPowerShell

# 动态增加模块搜索路径
sys.path.append(os.getcwd())


def getAllMp4InDirs(mp4_dirs, min_size=1.5 * 1e9):
    '''
    根据路径列表,获取其中的mp4文件完整路径
    :param mp4_dirs: mp4文件存在的路径列表, 列表中每个元素都是一个完整路径
    :param min_size: 过滤的mp4文件最小体积, 默认为1.2GB, 即小于1.2GB的mp4文件不显示
    :return: 所有大于最小体积的mp4文件
    '''
    all_mp4_files = []
    for mp4_dir in mp4_dirs:
        for root, dirs, files in os.walk(mp4_dir):
            mp4_files = [os.path.join(root, f) for f in files \
                         if f.endswith("mp4") and os.path.getsize(os.path.join(root, f)) > 1200000000 \
                         and "batch_merged" not in f]
            all_mp4_files.extend(mp4_files)
    return all_mp4_files


def getConvertedFilename(file, addition="batch_merged"):
    """
    获得转换后的完整文件名
    """
    dirname, filename = os.path.split(file)
    base, ext = os.path.splitext(filename)
    return os.path.join(dirname, base + "_" + addition + ext)


def getTimeClip(start_time=0, end_time=600, sample_rate=45, coverage=0.16, fixed_duration=0):
    """
    获得采样的时刻分布
    :param start_time: 采样开始时刻, 单位为秒, 默认为0, 即从一开始就采样
    :param end_time: 采样结束时刻, 单位为秒
    :param sample_rate:采样频率, 例如该值为100, 则表示每隔100秒开始采样1段, 如果共有1000秒(16分钟), 则采10个样
    :param coverage:剪辑覆盖率, 例如共1000秒,剪辑覆盖率为0.2, 那么最终只采集1000*0.2=200秒的时长
    :param fixed_duration:固定时长, 单位为秒，如果该值大于0，则不用剪辑覆盖率，而是按照固定时长采集片段
    :return:
    """
    sections = []
    duration = end_time - start_time  # 得到总时长
    clip_duration = duration * coverage  # 剪辑的总时长
    # 剪辑的总部分数, 向上取整,保证哪怕是0.1, 至少也能剪辑1段
    section_num = math.ceil(duration / sample_rate)
    average_section_duration = clip_duration / section_num  # 每部分平均时长
    print("一共剪辑为{0}段视频, 每段视频长度为{1}秒".format(section_num, average_section_duration))
    for i in range(section_num):
        # 获得每段开始时间
        section_start_time = duration / section_num * i
        # 获得每段用时, 先用平均时长表示, 如果固定时长大于0，则用固定时长
        section_duration = average_section_duration
        if fixed_duration > 0:
            section_duration = fixed_duration
        sections.append((start_time + section_start_time, start_time + section_start_time + section_duration))
    return sections


def clipVideo(file, start_time, end_time, i, is_accurate=False):
    """
    从视频中抽取片段
    :param file: 待分割的视频路径,例如r'F:\兴趣\图片\VR\其他\IPVR-071\IPVR-071-C.mp4'
    :param start_time: 开始时间, 以秒计, 例如10分钟就是600
    :param end_time: 结束时间, 同样以秒计算
    :param i: 视频片段是第几个, 例如4
    :return: 生成ffmpeg命令后, 在在命令行中执行, 得到视频片段的完整路径
    """
    dirname, filename = os.path.split(file)  # 解析文件路径和文件名
    base, ext = os.path.splitext(filename)  # 解析文件名的base和扩展名(.mp4)部分
    # 得到视频片段存储的完整路径, 默认与文件路径同级, 在后面增加seg_1, seg_2等
    clip_video_name = os.path.join(dirname, base + "_seg_" + str(i) + ext)
    # 指定视频中剪切一部分的命令模板
    clip_comand_template = "ffmpeg -hide_banner -ss '{0}' -i '{1}' -t '{2}' \
-avoid_negative_ts make_zero -c copy -map '0:0' -map '0:1' -map_metadata 0 -movflags '+faststart' \
-ignore_unknown -strict experimental -f mp4 -y '{3}'"
    # 生成命令
    expect_duration = end_time - start_time
    clip_command = clip_comand_template.format(start_time, file, end_time - start_time, clip_video_name)
    runWithPowerShell(clip_command)  # 在powershell中运行提取视频片段的命令
    # 如果不要求文件长度的精度，则直接返回文件
    if not is_accurate:
        return clip_video_name
    # 要求文件长度精度，则获取生成文件长度，如果时长太长，则删除文件并跳过
    file_duration = getVideoDuration(clip_video_name)  # 文件长度
    if file_duration < (2 * expect_duration):
        return clip_video_name
    os.remove(clip_video_name)
    return None


def sort_shuffle(l, circle=3):
    new_l = []
    for start_i in range(circle):
        i = start_i
        while (1):
            if i < len(l):
                new_l.append(l[i])
                i += circle
            else:
                break
    return new_l


def mergeVideos(file, segment_files, merged_filename, is_random=False):
    """
    批量合并文件
    :param file: 原始文件位置
    :param segment_files: 视频片段的列表, 里面每个元素是完整路径
    :param merged_filename: 合并的文件名, 为完整路径
    :return:
    """
    if is_random:
        # random.shuffle(segment_files)
        segment_files = sort_shuffle(segment_files)
    dirname, filename = os.path.split(file)
    merge_file_name = "merge_list.txt"
    # 得到合并列表txt的完整路径
    merge_txt = os.path.join(dirname, merge_file_name)
    with open(merge_txt, encoding="gbk", mode='w+') as mfile:
        for segment in segment_files:
            mfile.write("file '{0}'\n".format(segment))
    merge_cmd_template = "ffmpeg -hide_banner -f 'concat' -safe '0' -protocol_whitelist 'file,http,https,tcp,tls' -i \
'{0}' -c copy -movflags +faststart -ignore_unknown -y '{1}'"
    merge_cmd = merge_cmd_template.format(merge_txt, merged_filename)
    runWithPowerShell(merge_cmd)
    sleep(3)  # 休眠3秒钟
    # 删除不需要的文件
    os.remove(merge_txt)
    for segment in segment_files:
        os.remove(segment)


def getVideoDuration(video_file):
    """
    获取视频长度
    :param video_file: 视频文件
    :return:
    """
    video_duration = 0
    # 获取video时长和视频长宽
    with mpy.VideoFileClip(video_file) as video:
        video_duration = video.duration
    return video_duration


def getVideoSectionsStrategy(video_file, is_random=False):
    """
    获取视频策略，如果视频时长大于
    :param video_file:
    :return:
    """
    # 获取video时长和视频长宽
    with mpy.VideoFileClip(video_file) as video:
        video_size = video.size
        video_duration = video.duration
    if is_random:
        sample_time = video_duration / 80
        return getTimeClip(60, video_duration - 30, sample_time, fixed_duration=5)
    if video_duration > 1.4 * 3600:
        # 如果视频时长大于1小时24分钟，则应该是普通片，则将其分为100段，获得采样间隔时间
        sample_time = video_duration / 100
        return getTimeClip(20, video_duration, sample_time, 0.2)
    else:
        return getTimeClip(8, video_duration)


if __name__ == "__main__":
    mp4_dirs = [r"F:\other\兴趣\图片\VR\新建文件夹"]
    is_random = True  # 是否随机，像预告片那样进行切割
    all_mp4_files = getAllMp4InDirs(mp4_dirs)  # 获得所有mp4文件
    for file in all_mp4_files:
        # 打印log信息
        print("正在处理视频{0}".format(file))
        sections = getVideoSectionsStrategy(file, is_random=is_random)
        video_segments_files = []
        i = 1  # 从第1个片段开始
        for start_time, end_time in sections:
            # 抽取视频片段
            segment_file = clipVideo(file, start_time, end_time, i, is_accurate=is_random)
            if segment_file: video_segments_files.append(segment_file)
            i += 1
        # 合成整个视频
        converted_filename = getConvertedFilename(file, "预告片")  # 获得转换后的文件完整路径
        mergeVideos(file, video_segments_files, converted_filename, is_random=is_random)

# 从 git 复现 reid - clothes 部分
_本文件为在 Intel NUC 1 上部署 Clothes detection 的实际操作步骤。部署过程在 Reid Pose 之后，使用了其中建立的环境，如果在新环境中运行出现依赖问题，可查阅 person 及 pose 复现文档。以下步骤参照 README 文件执行，可作为其补充。_

## 1. 从百度云下载权重
>地址1：https://pan.baidu.com/s/1AT7tL9vNzFKGN4cQpKWusQ   
提取码：1234

下载文件 `obj_4000.weights`，上传至目录 `./clo_yolo/`。

地址2：https://pan.baidu.com/s/1ZI_UVUsPC9NKPFmjyF4MiQ  
提取码：1234

下载文件 `checkpoint.rar`，重新压缩为 `.zip` 格式后上传至目录 `./deep_sort/deep/`，使用 `unzip` 解压。
```sh
cd deep_sort/deep/
unzip checkpoint.zip
cd ../..
```

## 2. 安装环境
根据 pose 部分的经验，先查看 `requirements.txt` 文件内容。看到其中版本均为大于等于最低值的约束类型，且大多数在之前的安装过程中都有安装过，所以继续使用之前的环境：
```sh
conda activate reid0406
```
由于 `requirements.txt` 中有版本要求的项目不是很多，所以考虑先与当前环境中已有的版本对比确定是否需要重新安装。打印当前环境：
```sh
pip list
```
对比发现所有包均已经安装符合要求。为了确认可以执行安装步骤：
```sh
pip install -r requirements.txt
```
输出显示均为 `requirement already satisfied`。

## 3. 选择待测视频
在运行前先在文件中搜索发现不存在可以作为输入的 `.mp4` 格式测试视频：
```sh
find . -name '*.mp4'
```
所以接下来需要选择上传测试视频。本例中继续使用之前 person 人物的视频，所以直接用命令复制到当前目录下。
```sh
cp ../Person_reid_ARM_X86/input_reid.mp4 ./input_reid.mp4
cp ../Person_reid_ARM_X86/test.mp4 ./test.mp4
ls
```
两个视频内容如下：
|文件名|来源|时长|帧率|
|:---|:---|:---:|:---:|
|input_reid.mp4|hws 提供的 “4_5_内容汇总/之前各项人物的汇报资料/input_reid.mp4”|12s|29.79/s|
|test.mp4|buaa 项目中的 "ori.mp4"|26s|24.00/s|

因为视频中均没有特别的服装出现，所以之后使用时长较短的 `input_reid.mp4` 进行测试，最后附上 `test.mp4` 的结果。

## 4. 测试
根据 person 部分的经验，查看 `reid_clothes.py` 文件。根据内容推测其应当与 person 部分相同，、不会将结果保存为 `.mp4` 或 `.avi` 类型的视频文件。但是仍然先运行：
```sh
python3 reid_clothes.py --video_path 'input_reid.mp4'
```
此时有报错：
```sh
FileNotFoundError: [Errno 2] No such file or directory: './deep_sort/deep/checkpoint/ckpt.t7'
```
发现之前的压缩文件含有两层 checkpoint 目录，所以将内容移到外层中：
```sh
cp -r deep_sort/deep/checkpoint/checkpoint/ deep_sort/deep/
rm -r deep_sort/deep/checkpoint/checkpoint/
```
重新运行正常，此时与预料相同观察不到输出，所以参照 person 部分的经验修改代码。
> 以下行号为修改后的位置，请在其前后合适位置修改并注意调整缩进。
第 189 至 191 行添加：
```python
        temp_path, vid_writer = None, None
        fourcc='mp4v'
        save_path = './output.mp4'
```
第 368 至 377 行添加：
```python
            if temp_path != save_path:  # new video
                temp_path = save_path
                if isinstance(vid_writer, cv2.VideoWriter):
                    vid_writer.release()  # release previous video writer
    
                fps = vid_cap.get(cv2.CAP_PROP_FPS)
                width = int(vid_cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                height = int(vid_cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                vid_writer = cv2.VideoWriter(save_path, cv2.VideoWriter_fourcc(*fourcc), fps, (width, height))
            vid_writer.write(ori_img)
```
此时可查看结果，准确率较低。
> `test.mp4` 对应结果保存为 `output_0.mp4`

## 5. 其他修改
在 README 文件中存在两项其他修改：

- (a) 修改 torch 包的 unsampling.py 文件：

> 因为目前 torch 没有报错，所以尽量不修改其内容，以保证其他算法在此环境下能正常运行。

- (b) 修改 reid_clothes.py 的 265 行附近内容：

> 上网查阅资料发现确实有很多代码是按照修改后的样式书写的。按建议修改后尝试运行，此时报错：
```sh
IndexError: invalid index to scalar variable.
```
> 所以放弃修改，该问题可能由环境版本不一致导致。

另外在 README 中提到也可以运行另一个文件 `no_reid_clothes.py`。简单查看代码发现其在第 248 行与原代码 `reid_clothes.py` 有区别，效果是不会画出人物识别框，仅画出服装识别结果。修改 `reid_clothes.py` 目前的第 251 行即可达到此效果。
```python
# ori_img = draw_boxes(ori_img, bbox_xyxy, identities)
```
运行 `no_reid_clothes.py` 没有报错，不再进一步修改该代码。
> `input_reid.mp4` 对应不显示人物框的识别结果保存为 `output.mp4`。

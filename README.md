# Clothes_detection_ARM

## This project is suitable for both ARM and x86 environment.



### Some of the files were not uploaded because they were too large:

```shell
./clo_yolo/obj_4000.weights ./deep_sort/deep/checkpoint
```

The download link of these files are:

For the `./clo_yolo/obj_4000.weights` the link is : `https://pan.baidu.com/s/1AT7tL9vNzFKGN4cQpKWusQ` And the password is : `1234`

or you can try this link to download the file : `https://drive.google.com/file/d/1SnxWsylT3sVpSkTvsPV_Alxdv6YgUz15/view?usp=sharing`



For the `./deep_sort/deep/checkpoint` the link is : `https://pan.baidu.com/s/1ZI_UVUsPC9NKPFmjyF4MiQ` And the password is : `1234`

or you can try this link to download the file : `https://drive.google.com/file/d/1QYQ6I3j8iwXWwnV6uKbKosRkzCpUpBdv/view?usp=sharing`





**The python version of these project is 3.7**

After download these weights file and put it to the correct place, we should run this command to setup our environment.

```shell
pip install requirement.txt
```

use the command :

```shell
python3 reid_clothes.py --video_path 'your video path'
```

if you have this problem ：

```shell
ImportError: libGL.so.1: cannot open shared object file: No such file or directory
```

Then use this command to install opencv-python-headless :

```shell
pip install opencv-python-headless
```

After install all the dependences of the project. We should go to our virtual environment path:

```shell
cd your_virtual_environment_path/lib/lib/python3.7/site-packages/torch/nn/modules/upsampling.py
```

And change the `upsampling.py` file. In line 152:

```python
def forward(self, input: Tensor) -> Tensor:
# 	return F.interpolate(input, self.size, self.scale_factor, self.mode, self.align_corners, recompute_scale_factor=self.recompute_scale_factor)
	return F.interpolate(input, self.size, self.scale_factor, self.mode, self.align_corners)
```

And if your environment is x86 environment, please open the `reid_clothes.py` file to the file 265:

```python
ln = self.clo_net1.getLayerNames()
# ln = [ln[i - 1] for i in self.clo_net1.getUnconnectedOutLayers()]
ln = [ln[i[0] - 1] for i in self.clo_net1.getUnconnectedOutLayers()]
```



Finally, we only should use these command to run the project.

```shell
python3 reid_clothes.py --video_path 'your video path'
```

or

```shell
python3 no_reid_clothes.py.py --video_path 'your video path'
```

For the camera as input option, we will add it in a later optimization.

## PACN
像素注意力卷积神经网络单幅图像超分辨率重建
## Dependencies
* Python 3.6
* PyTorch >= 1.0.0
* numpy
* skimage
* **imageio**
* matplotlib
* tqdm
## Code
Clone this repository into any place you want.
```bash
git clone https://github.com/pacn2020/PACN
cd PACN
```
## Quickstart (Demo)
Run the script in ``src`` folder. Before you run the demo, please uncomment the appropriate line in ```demo.sh``` that you want to execute.
```bash
cd src       # You are now in */PACN/src
sh demo.sh
-------------
#训练
python main.py --model PACN --save pacn_X2 --scale 2 --reset --save_results --patch_size 96
python main.py --model PACN --save pacn_X3 --scale 3 --reset --save_results --patch_size 144
python main.py --model PACN --save pacn_X4 --scale 4 --reset --save_results --patch_size 192
#测试
python main.py --model PACN --data_test Manga109 --scale 2 --pre_train ../experiment/model/pacn_X2.pt --test_only --save_results
----------------



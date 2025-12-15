# Camie V2 本地模型文件

请手动下载以下文件并放到这个目录：

1. **模型文件** (789 MB)：
   - 下载地址：https://huggingface.co/Camais03/camie-tagger-v2/resolve/main/camie-tagger-v2.onnx
   - 保存为：`camie-tagger-v2.onnx`

2. **元数据文件** (7.77 MB)：
   - 下载地址：https://huggingface.co/Camais03/camie-tagger-v2/resolve/main/camie-tagger-v2-metadata.json
   - 保存为：`camie-tagger-v2-metadata.json`

## 下载方法

### 方法 1：使用浏览器直接下载
直接点击上面的链接，浏览器会开始下载。

### 方法 2：使用 wget（如果已安装）
```powershell
cd models\camie-v2
wget https://huggingface.co/Camais03/camie-tagger-v2/resolve/main/camie-tagger-v2.onnx
wget https://huggingface.co/Camais03/camie-tagger-v2/resolve/main/camie-tagger-v2-metadata.json
```

### 方法 3：使用 curl
```powershell
cd models\camie-v2
curl -L -o camie-tagger-v2.onnx https://huggingface.co/Camais03/camie-tagger-v2/resolve/main/camie-tagger-v2.onnx
curl -L -o camie-tagger-v2-metadata.json https://huggingface.co/Camais03/camie-tagger-v2/resolve/main/camie-tagger-v2-metadata.json
```

## 验证

下载完成后，这个目录应该包含：
```
models/camie-v2/
├── README.md (本文件)
├── camie-tagger-v2.onnx (789 MB)
└── camie-tagger-v2-metadata.json (7.77 MB)
```

然后就可以运行：
```powershell
python compare_taggers.py .\download\image.jpg --tagger1 wd14 --tagger2 camie_v2
```

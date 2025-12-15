# Tagger 对比工具使用说明

## 概述

`compare_taggers.py` 是一个用于对比不同 tagger 模型输出结果的工具。它可以帮助你：

1. 对比两个不同 tagger 的标签输出差异
2. 查看每个 tagger 独有的标签
3. 对比相同标签的置信度差异
4. 批量处理目录中的所有图片
5. 导出对比结果为 JSON 文件

## 可用的 Tagger

### 1. WD14 (wd14)
- **模型**: WD14 EVA02-Large
- **标签数量**: ~9,000 个标签
- **特点**: 
  - 高准确度的通用标签
  - 优秀的图片特征识别
  - GPU 加速支持
- **适用场景**: 通用图片标注、Stable Diffusion 训练

### 2. ML-Danbooru (mldanbooru)
- **模型**: ML-Danbooru Caformer
- **标签数量**: 12,547 个标签
- **特点**:
  - Danbooru 风格标签
  - Caformer 架构
  - 更细粒度的分类
- **适用场景**: Danbooru 风格标注、详细特征识别

### 3. Camie (camie)
- **模型**: Camie Tagger
- **标签数量**: 70,000+ 个标签
- **特点**:
  - 最全面的标签覆盖
  - 包含 rating、general、character 分类
  - 多种预测模式（balanced、high_precision、high_recall 等）
- **适用场景**: 需要详细标注、角色识别、评级分类

## 基本用法

### 1. 单张图片对比

```bash
# 对比 WD14 和 Camie
python compare_taggers.py image.png --tagger1 wd14 --tagger2 camie

# 使用自定义阈值
python compare_taggers.py image.png --tagger1 wd14 --tagger2 camie --threshold 0.5

# 显示共同标签的置信度差异
python compare_taggers.py image.png --tagger1 wd14 --tagger2 camie --show-common
```

### 2. 对比 WD14 和 ML-Danbooru

```bash
python compare_taggers.py image.png --tagger1 wd14 --tagger2 mldanbooru
```

### 3. 批量处理目录

```bash
# 递归处理目录
python compare_taggers.py ./download --recursive --tagger1 wd14 --tagger2 camie

# 仅处理当前目录
python compare_taggers.py ./download --tagger1 wd14 --tagger2 camie
```

### 4. 导出对比结果

```bash
# 单个文件导出为 JSON
python compare_taggers.py image.png --tagger1 wd14 --tagger2 camie --export comparison.json

# 批量导出到目录
python compare_taggers.py ./download --recursive --tagger1 wd14 --tagger2 camie --export ./comparisons
```

## 高级用法

### 自定义模型参数

```bash
# WD14 使用不同模型
python compare_taggers.py image.png --tagger1 wd14 --model1 ViT_Large --tagger2 camie

# Camie 使用高精度模式
python compare_taggers.py image.png --tagger1 wd14 --tagger2 camie --model2 high_precision
```

### Camie 模式说明

- `balanced`: 平衡精确率和召回率（默认）
- `high_precision`: 高精确率，更少误报
- `high_recall`: 高召回率，更全面但可能有误报
- `micro_opt`: 微调优化
- `macro_opt`: 宏调优化

### 阈值调整

```bash
# 调整通用标签阈值
python compare_taggers.py image.png --threshold 0.5

# 调整角色标签阈值
python compare_taggers.py image.png --character-threshold 0.9

# 同时调整两个阈值
python compare_taggers.py image.png -t 0.4 -c 0.85
```

## 输出说明

对比结果包含以下信息：

### 1. 文件元数据
- **ComfyUI 检测**: 是否为 ComfyUI 生成的图片
- **URL 推断**: 从文件名推断的源 URL
- **动图处理**: 是否使用了静态版本进行标注

### 2. Tagger 统计
- 标签数量
- 处理时间
- 错误信息（如果有）

### 3. 标签差异
- **Only in Tagger1**: 仅在第一个 tagger 中出现的标签
- **Only in Tagger2**: 仅在第二个 tagger 中出现的标签
- **Common tags**: 两个 tagger 都识别的标签（使用 `--show-common` 显示）

### 4. 统计摘要
- 共同标签数量
- 各自独有标签数量
- 标签重叠率（overlap percentage）

## JSON 导出格式

```json
{
  "file_path": "image.png",
  "is_comfyui": false,
  "inferred_url": "https://www.pixiv.net/artworks/12345",
  "used_static_for_animated": false,
  "tagger1": {
    "name": "wd14",
    "model": "WD14-EVA02_Large",
    "tags": {
      "1girl": 0.95,
      "solo": 0.89,
      ...
    },
    "processing_time": 2.5
  },
  "tagger2": {
    "name": "camie",
    "model": "Camie-balanced",
    "tags": {
      "1girl": 0.92,
      "solo": 0.87,
      ...
    },
    "processing_time": 3.2
  },
  "comparison": {
    "only_in_tagger1": ["tag1", "tag2", ...],
    "only_in_tagger2": ["tag3", "tag4", ...],
    "common_tags": ["1girl", "solo", ...],
    "confidence_diff": {
      "1girl": {
        "tagger1": 0.95,
        "tagger2": 0.92,
        "diff": 0.03
      }
    }
  }
}
```

## 使用场景

### 1. 选择最适合的 Tagger

对比不同 tagger 在你的数据集上的表现，选择最适合的模型。

```bash
# 对比多个图片
python compare_taggers.py ./sample_images --recursive --tagger1 wd14 --tagger2 camie --export ./comparison_results
```

### 2. 标签质量评估

检查不同 tagger 对同一图片的标注差异，评估标签质量。

```bash
# 显示共同标签的置信度差异
python compare_taggers.py image.png --tagger1 wd14 --tagger2 camie --show-common
```

### 3. 寻找漏标

查看各个 tagger 的独有标签，可能发现被其他 tagger 遗漏的重要特征。

```bash
# 使用较低阈值以获取更多标签
python compare_taggers.py image.png --tagger1 wd14 --tagger2 mldanbooru --threshold 0.3
```

### 4. 标签融合

导出对比结果，然后可以编写脚本合并不同 tagger 的优势。

```bash
python compare_taggers.py ./images --recursive --tagger1 wd14 --tagger2 camie --export ./merged_tags
```

## 代码重构说明

### utils.py 中的共享功能

以下功能已提取到 `utils.py`：

1. **图片处理**
   - `STATIC_IMAGE_EXTENSIONS`: 静态图片扩展名
   - `ANIMATED_IMAGE_EXTENSIONS`: 动图扩展名
   - `ALL_IMAGE_EXTENSIONS`: 所有支持的图片扩展名

2. **ComfyUI 检测**
   - `is_comfy_image()`: 检测是否为 ComfyUI 生成的图片
   - `get_comfy_filename()`: 生成 .comfy 后缀的文件名

3. **URL 推断**
   - `URL_PATTERNS`: 文件名到 URL 的正则表达式模式
   - `infer_url_from_filename()`: 从文件名推断源 URL

4. **动图处理**
   - `find_static_version()`: 为动图寻找静态版本

这样做的好处：
- 代码复用，减少重复
- 统一行为，确保一致性
- 易于维护和测试

## 性能提示

1. **GPU 加速**: 确保安装了 `onnxruntime-gpu` 和 CUDA 依赖
2. **批量处理**: 使用目录模式而非逐个文件处理
3. **阈值调整**: 提高阈值可以减少标签数量，提升处理速度
4. **选择性导出**: 只在需要时使用 `--export`

## 故障排查

### CUDA 错误

如果看到 CUDA 相关错误，但程序仍然运行，说明正在使用 CPU。这不影响功能，只是速度较慢。

要启用 GPU：
```bash
pip install onnxruntime-gpu==1.23.2
pip install nvidia-cuda-runtime-cu12 nvidia-cudnn-cu12
```

### 内存不足

处理大量图片时可能遇到内存问题：
- 减少批量大小
- 提高阈值以减少标签数量
- 分批处理目录

### 标签数量差异大

不同 tagger 的标签数量差异是正常的：
- WD14: 较少但精准的标签
- ML-Danbooru: 中等数量，Danbooru 风格
- Camie: 最多标签，最全面

可以通过调整阈值来平衡标签数量。

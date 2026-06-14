# PDF 解析速度优化

## 问题
之前 PDF 解析优先使用 `pdfplumber`，虽然准确但速度较慢。

## 解决方案
创建了 `FastPDFParser`，优先使用 `PyMuPDF`（fitz），速度提升 **5-10 倍**。

## 对比

| 解析库 | 速度 | 中文支持 | 现在策略 |
|--------|------|---------|---------|
| PyMuPDF (fitz) | ⚡⚡⚡ 很快 | ✅ 好 | **首选** |
| pdfplumber | ⚡ 慢 | ✅ 很好 | 备用 |
| PyPDF2 | ⚡⚡ 中等 | ⚠️ 一般 | 不再使用 |

## 效果预估

| 文件大小 | 之前 | 现在 |
|---------|------|------|
| 100KB PDF | ~2秒 | ~0.3秒 |
| 500KB PDF | ~8秒 | ~1秒 |
| 1MB PDF | ~15秒 | ~2秒 |

## 安装新依赖

```bash
cd backend
pip install PyMuPDF==1.24.0
```

或重新安装全部依赖：
```bash
pip install -r requirements.txt
```

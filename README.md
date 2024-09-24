# Quick File Deletion

## 简介

Quick File Deletion 是一个用于快速删除文件和目录的工具。它提供了一个简单易用的图形用户界面，用户可以通过拖放文件或目录来进行删除操作。删除的文件和目录不会进入回收站，且无法恢复，因此请谨慎使用。

## 功能

- 拖放文件或目录进行快速删除
- 删除历史记录
- 目录预览和搜索功能
- 日志记录

## 安装

### 先决条件

- Python 3.6 及以上版本
- 需要安装以下 Python 库：
  - `tkinter`
  - `tkinterdnd2`
  - `asyncio`

### 安装步骤

1. 克隆或下载本项目到本地：

   ```bash
   git clone https://github.com/XIYBHK/Quick-file-deletion.git
   cd Quick-file-deletion
   ```

2. 安装所需的 Python 库：

   ```bash
   pip install tkinter tkinterdnd2 asyncio
   ```

## 使用说明

1. 运行 `delete_file.py` 文件：

   ```bash
   python filedel/delete_file.py
   ```

2. 打开程序后，将需要删除的文件或目录拖放到指定区域。

3. 确认删除操作，文件或目录将被永久删除。

4. 可以在删除历史中查看已删除的文件和目录，并使用搜索功能查找特定文件。

## 常见问题

### 1. 如何恢复误删的文件？

由于本工具的删除操作不会经过回收站，且无法恢复，因此请谨慎使用。如果误删了重要文件，建议使用专业的数据恢复工具尝试恢复。

### 2. 为什么删除操作没有反应？

请确保您拖放的文件或目录路径正确。如果问题仍然存在，请查看日志文件 `delete_file.log` 以获取更多信息。

### 3. 如何清空删除历史？

在删除历史界面，点击“清空历史”按钮即可清空所有删除记录。

## 贡献

欢迎对本项目进行贡献！如果您有任何建议或发现了 bug，请提交 issue 或 pull request。

## 许可证

本项目采用 MIT 许可证。详情请参阅 LICENSE 文件。

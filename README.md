# Games Bot v1.0 — 自动点击工具

为 **Panoptyca** 游戏设计的桌面自动化点击工具。基于 OpenCV 模板匹配识别游戏按钮，按用户配置的顺序循环点击。

## 快速启动

### 方式一：双击 EXE（推荐）

`build_output/GamesBot.exe` — 单文件，无需安装 Python，放到任意位置运行。

### 方式二：Python 源码

```bash
pip install -r requirements.txt
python main.py
```

## 新功能 (v1.0)

### 防锁屏 & 自动关屏
- **防锁屏**：bot 运行时自动阻止 Windows 锁屏（AwayMode），屏幕可正常黑屏但不锁
- **轮间关屏**：每轮完成后自动关显示器省电，下一轮开始前自动唤醒
- **黑屏检测**：运行时检测到屏幕关闭会自动唤醒并重启轮次
- bot 停止后恢复默认电源策略

### 窗口自动激活
- 20 次连续匹配失败 → 自动切游戏窗口到前台（Alt 键 + SetForegroundWindow + Alt+Tab 兜底）

### PyInstaller 打包
- 单文件 EXE，无需安装 Python 环境
- 内置模板和配置，随处运行

## 整体架构

```
Games Bot/
├── main.py                 # 入口（支持 PyInstaller 路径）
├── settings.json           # 持久化配置
├── requirements.txt        # Python 依赖
├── build_exe.bat           # EXE 打包脚本
├── config/
│   └── manager.py          # ConfigManager — JSON 配置读写
├── engine/
│   ├── matcher.py          # match_template — OpenCV 模板匹配
│   ├── clicker.py          # ClickEngine — 核心点击循环
│   └── lock_detect.py      # 锁屏检测工具
├── ui/
│   ├── styles.py           # Qt 样式表
│   ├── floating_window.py  # 悬浮窗口 UI
│   └── calibrator.py       # 截图校准叠加层
└── templates/              # 模板图片
```

## 配置说明（settings.json）

```json
{
  "threshold": 0.6,            // 模板匹配阈值 0.0~1.0
  "baseline_width": 1920,       // 基准分辨率
  "baseline_height": 1080,
  "actions": [                  // 点击顺序列表
    {
      "name": "button_1",
      "template": "templates/button_1.png",
      "post_delay": 1.0,        // 点击后等待秒数
      "timeout": 1              // 每按钮超时秒数
    }
  ],
  "round_interval": 30,         // 每轮间隔秒数
  "window_geometry": { "x": 100, "y": 100, "collapsed": false }
}
```

## UI 功能

- ▶ 运行 / ⏹ 停止
- 📷 截取新模板
- 拖拽排序按钮顺序
- 阈值 / 轮次间隔可调
- 状态显示：当前轮次 / 按钮名 / 进度 / 倒计时
- ▲ 收起 / ▼ 展开配置面板

## 模板截图流程

1. 点击 📷 或 + 截取模板添加
2. 全屏覆盖层出现，拖拽框选按钮区域
3. 松开 → 裁剪保存到 templates/
4. 自动添加到 actions 列表末尾

## 构建 EXE

以管理员身份运行 `build_exe.bat`，输出到 `build_output/GamesBot.exe`。

## 版本管理

```bash
git log                    # 看历史
git reset --hard <hash>    # 回退任意版本
```

---
name: 文生图助手
description: 把用户描述转成可下载图片，强调构图与风格约束。
trigger_keywords:
  - 画一张
  - 文生图
  - 生成图片
  - generate image
  - 出图
trigger_intent: 根据文字描述生成图片文件
tools:
  - builtin: generate_image
  - local: generate_image
workflow:
  - step: 1
    action: 澄清主体、风格、画幅、禁忌内容
  - step: 2
    action: 调用 generate_image
    expect: 返回 download_url
  - step: 3
    action: 把下载链接交给用户，并简述构图选择
confidence: 0.95
---

接到文生图请求时：

1. 先把模糊描述改写成具体 prompt（主体、镜头、光线、风格、负面约束）。
2. 必须调用 `generate_image`（内置）或本包工具 `pack__nous_image_gen__generate_image`，不要假装已经生成。
3. 成功后原样给出 `download_url`，并简短说明构图选择。
4. 若工具报缺少 IMAGE_API_KEY / Bedrock 模型权限，明确说明原因，不要编造图片链接。

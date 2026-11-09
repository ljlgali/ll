---
name: 小小加密
description: 简单的文本加密与解密工具
---

# 小小加密 Skill

当用户要求加密、解密、编码、解码一段文本时调用本 Skill。

## 支持的加密方式

| 方式 | 说明 |
|------|------|
| Caesar | 凯撒密码，字母按位移量替换 |
| Base64 | 标准 Base64 编码 |
| ROT13 | ROT13 字母替换 |

## 执行步骤

1. 确认用户要加密还是解密
2. 确认使用哪种方式（用户没指定时默认 Caesar 位移 3）
3. 调用 `RunCli` 执行 Python 一行脚本完成加密/解密
4. 把结果清晰输出给用户

## 示例（Caesar 加密，位移 3）

```python
text = "HELLO"
shift = 3
result = ''.join(chr((ord(c) - ord('A') + shift) % 26 + ord('A')) for c in text)
print(result)  # KHOOR
```

"""抖音 Web 签名（a_bogus + websign），纯 Python。
原样摘自 Evil0ctal/Douyin_TikTok_Download_API（Apache-2.0）src/dtk/signing/native/，
提交 b5505e3（2026-10-27），仅把包内 import 改成相对路径。版权归原作者，见 LICENSE-Apache-2.0。
平台更新签名后这里会失效：去上游仓库拉新版 abogus.py / websign.py / sm3.py 覆盖即可。"""

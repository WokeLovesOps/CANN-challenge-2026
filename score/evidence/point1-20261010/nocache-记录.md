# 点1：输入禁用L2缓存

正式基线源码9adcc9d。补丁相对baseline.asc，恢复补丁即得完整候选源码。

随机、全负、全零、抵消输入四场景均双调用正确，第二调用改变输入；每场景两份BIN。模型冷0.81μs、热0.75μs。未有收益，不提交OJ。

源/库/BIN哈希在同名models.json；热调用指令次数在instructions.json。原始BIN和CSV在Build/point1-20261010/sim，不包含于Git归档。

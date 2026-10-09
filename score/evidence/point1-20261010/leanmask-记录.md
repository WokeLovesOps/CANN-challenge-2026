# 点1：固定repeat版删减初始掩码

在reuse版本上只删除初始ResetMask，补丁相对baseline.asc提供完整可恢复差异。四场景双调用完整正确，两份有效BIN；模型冷0.61μs、热0.54μs，无收益，不送OJ。正式源码仍为9adcc9d。

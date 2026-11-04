# ERP 配对验证方案

2026-11-01。用户回复 "C批准"，批准 ERP_PAIRED_PLAN.approved.md 的 24 个请求、144 个正式 session、Haiku 5.5、答案字段为主要终点、不加可选项。本文件是该方案的执行版。正式 session 尚未启动，formal_authorized 为 false，发布授权为 false。开跑前要先完成公开存档。还有四件事等用户决定，写在 STATE.json 的 decisions_needed 里，本文件按当前默认状态写。

## 研究问题

agent 从公共仓库里的 BIDS 数据出发，按给定计划做 ERP 分析时，带 AEA 是否比不带 AEA 更常得到和认证参考一致的答案。

这个对照估计的是整个 AEA 包的作用，包括领域内容、模板、工具和组织方式，不单独识别 skill 格式本身的效果。计划由研究者事先给定，所以结果不能说明 agent 能自主选出更好的方法，也不能推断节省了研究者的时间。

## 数据

| 项目 | 内容 |
|---|---|
| 来源 | ERP CORE，DOI 10.18115/D5JW4R，OSF BIDS 组件 https://osf.io/9f5w7/ ，数据集 CHANGES 写明版本 1.0 |
| 本地路径 | /home/hou/Research/data/raw/erpcore_osf_9f5w7/ERP_CORE_BIDS_Raw_Files，保留 OSF 的目录结构，形如 sub-021/ses-P3/eeg/ |
| 下载范围 | 全部顶层文件，40 名被试的 P3、N170、ERN、N400 四个任务，共 1,133 个文件，12.58 GB |
| 未下载 | code、stimuli 文件夹和 MMN、N2pc、LRP 任务，这个实验用不到 |
| 清单 | data_prep/DATA_MANIFEST.json 记录来源和每个文件的 OSF 编号、大小、md5、sha256 |
| agent 看到的 | 这棵目录树的只读挂载 /input/erp_core_bids，加上 DOI 和 OSF 组件地址 |

本地已有的 sub-001 到 sub-020 共 485 个文件 md5 与 OSF 一致，直接复制，其余从 OSF 下载。挂载里有全部 40 人，agent 要自己按计划找到 sub-021 到 sub-040。

## 请求清单

合计 24 个。单被试规则在看任何模型结果之前固定，每个成分在 sub-021 到 sub-040 里按编号取前 5 名合格者，合格按 tab:spec 的 trial 门槛判定。四个成分在这 20 人里全部合格，ERN 的 15 trial 门槛也没有排除任何人。

| 成分 | BIDS 任务 | 单被试请求 | 组水平请求 |
|---|---|---|---|
| P3b | P3 | sub-021 到 sub-025 | sub-021 到 sub-040 |
| N170 | N170 | sub-021 到 sub-025 | sub-021 到 sub-040 |
| ERN | ERN | sub-021 到 sub-025 | sub-021 到 sub-040 |
| N400 | N400 | sub-021 到 sub-025 | sub-021 到 sub-040 |

每个请求带 AEA 和不带 AEA 各 3 次，共 144 个 session，配对顺序和配对内条件顺序按种子 20261101 随机，见 SCHEDULE.proposed.json。请求文件在 requests/，清单在 REQUESTS.json。

## 计划内容

两臂拿到逐字相同的任务指令和机器可读计划 PUBLIC_CONTRACT.json。计划写明 tab:spec 的全部设置。

| 设置 | P3b | N170 | ERN | N400 |
|---|---|---|---|---|
| 对比 | 罕见减频繁 | 面孔减汽车 | 错误减正确 | 无关减相关 |
| 时间锁定 | 刺激 | 刺激 | 反应 | 刺激 |
| 带通 (Hz) | 0.1 到 30 | 0.1 到 40 | 0.1 到 30 | 0.1 到 30 |
| 分段 (s) | −0.2 到 0.8 | −0.2 到 0.5 | −0.4 到 0.6 | −0.2 到 0.8 |
| 基线 (s) | −0.2 到 0 | −0.2 到 0 | −0.4 到 −0.2 | −0.2 到 0 |
| 剔除 | 无 | 无 | 无 | 无 |
| 最少 trial | 罕见 30，频繁 100 | 每条件 30 | 每条件 15 | 每条件 30 |
| ROI | Fz, Cz, Pz, CPz | PO7, PO8, P7, P8 | FCz, Fz, Cz | CPz, Cz, Pz |
| 时间窗 (s) | 0.30 到 0.50 | 0.13 到 0.20 | 0 到 0.10 | 0.30 到 0.50 |
| 方向 | 正 | 负 | 负 | 负 |

四个成分共用的设置是平均参考、零相位 FIR 带通（下过渡带 0.1 Hz，上过渡带用 MNE 默认规则）、重采样到 256 Hz。振幅取差异波在 ROI 和时间窗内的均值。组水平是 ROI 振幅对零的双侧单样本 t 检验，加同一时间窗上的单侧 cluster 置换检验（5000 次，成团阈值为单侧 t 的 0.95 分位，邻接用 MNE 的 find_ch_adjacency）。

计划没有给事件代码。agent 要读数据集里的 task-*_events.json 自己确定哪些代码构成每个条件。

有三处细节 tab:spec 没写，计划里补写了，因为不写就不是同一个计算。先去掉 HEOG_left、HEOG_right、VEOG_lower 三个眼电通道（读入时类型是 EEG），处理顺序是滤波、重采样、平均参考、分段，事件样本点用 events.tsv 的 onset 乘 256 取整。是否保留这几条的取舍写在 decisions_needed。

## 参考答案

参考答案由 v0.3.2 标签里的 validate_p3_group.py、validate_n170_erpcore_group.py、validate_ern_erpcore_group.py、validate_n400_erpcore_group.py 计算，原文件用 git show 取出放在 reference_code/v0.3.2/，分析函数和 main 都没有改。run_reference.py 只做三件事，把脚本的 DATA 常量指向只含目标被试的符号链接目录，包一层记录脚本已经返回的未取整值和波形，把工作目录放在本研究内。

分别在 MNE 1.12.1（aeais 环境，NumPy 2.4.6 这一套）和 agent 运行的 Apptainer 镜像（MNE 1.8.0）各算一次。20 人四成分的 ROI 振幅两环境最大差异是 1.9e-13 µV，远低于 0.1 µV，trial 数、合格名单和显著性判断全部相同。冻结参考取 MNE 1.12.1 的结果。同一套流程跑 sub-001 到 sub-020，和 v0.3.2 提交的认证结果逐人比较，三位小数完全一致，说明新下载的数据和这层包装没有改变结果。

参考数值不进计划、预加载包和资源快照，也不会传给 session。session 只绑定自己的工作目录和只读数据，没有网络。

## 终点

全部是确定性检查。LLM 判定关闭，StudyClient 拒绝 target 以外的角色，试跑账目里非 Haiku 请求为 0。

| 终点 | 角色 | 定义 |
|---|---|---|
| 答案字段 | 主要 | 单被试 ROI 振幅绝对误差不超过 0.1 µV；组水平的效应方向、t 检验显著性、cluster 显著性三项都和参考相同 |
| 完整合同 | 次要 | 答案字段，加 trial 数、被试名单、各人振幅、组均值、最终报告和文件一致、证据数组、衍生数据、版本和 DOI 全部通过 |
| 证据数组 | 次要 | analysis_evidence.npz 的时间轴一致，ROI 差异波与参考的 RMS 不超过 0.1 µV |
| BIDS-Derivatives | 次要 | /workspace/derivatives/erp-analysis 通过 bids-validator（jsr:@bids/validator@3.0.2，schema 1.2.7）且无错误，并且每名被试都有结果文件 |
| 版本和 DOI | 次要 | result.json 写了正确的 DOI 和 CHANGES 里的版本 1.0 |

答案优先取 result.json，缺失时取首次最终报告里的 JSON，来源记入 answer_source。这样缺文件和算错数分开计，缺文件仍会让完整合同不通过。

校准结果在 VERIFIER_TESTS.json。参考本身写成的交付和一个独立实现 plan_solution.py 的交付（只读公开计划，在 agent 镜像里运行）在全部 26 个请求上都通过主要终点和完整合同，后者与参考的最大振幅差是 1.9e-13 µV。188 个已知错误用例覆盖 34 类，包括振幅偏 0.2 µV、事件映射反了、ROI 错了（用真实波形算错 ROI 的值）、单位错、缺结果文件、缺证据、缺衍生数据、衍生数据不合规、DOI 或版本错，全部按预期判定。

## AEA 资源

新快照 aea-erp-r1-20261101 从 aea-postfailure-r3-20261031 建立，变更记录在 RESOURCE_FREEZE.json。

| 变更 | 文件 |
|---|---|
| 嵌套 BIDS 支持，--task 过滤，读 events.tsv 和 CHANGES | tools/auto_brief.py |
| BIDS-Derivatives 模板，已用 bids-validator 核实可通过 | templates/bids_derivatives/ |
| 衍生数据写入工具 | tools/write_erp_derivatives.py |
| ERP 输出结构自检，不含参考数值 | tools/check_erp_outputs.py |
| 索引和变更记录 | RESOURCE_INDEX.md、CHANGELOG.md |

没有删除文件，也没有改任何分析默认值。预加载由实验方按成分选，规则在 build_packets.py 开头，每个成分都给 eeg-preprocess、eeg-epoch、eeg-erp、eeg-stats 的 SKILL.md 和 references/procedure.md，加该成分的 recipe（p300-oddball、n170-faces、ern-flankers、n400-semantic）和 BIDS-Derivatives 模板说明，同一成分的单被试和组水平用同一份。包的长度约 11.7 万到 12.7 万字符，每次请求都核对完整包确实出现在发给模型的消息里。

不带 AEA 的一臂没有这些资源，其余相同。扫描结果在 RESOURCE_LEAK_SCAN.json，四个成分在 sub-021 到 sub-040 的参考数值没有出现在预加载包、计划文件或快照里。快照里出现这些被试编号的文件只涉及 MMN，继承自 r3。

## 运行参数

| 参数 | 取值 | 依据 |
|---|---|---|
| 模型 | claude-haiku-5-5，thinking 关闭，effort medium，每次最多 2,048 token | 沿用上一轮，已从试跑的真实请求字段核实，见 EXECUTION_CONFIG_WITNESS.json |
| 循环 | 上游 CodeAct 不改，最多 20 轮 | 沿用上一轮 |
| 单格时长 | 300 秒 | 最慢的 20 人参考脚本单线程 42.3 秒，约 7 倍 |
| 单 session 时长 | 1,200 秒 | 三次完整重跑加 20 轮模型调用，在慢一倍的节点上约 550 秒，再留一倍 |
| CPU | 每 session 2，核内线程 1 | 参考脚本 CPU 时间约等于墙钟时间，上限来自已批准方案 |
| 内存 | 单被试 8 GiB，组水平 16 GiB | 参考峰值 0.96 GiB，同时持有 20 份原始记录约 3.2 GiB；试跑整个作业峰值 2.9 GiB |

两臂相同。方案里担心官方 720 秒不够组水平任务，实测没有这个问题，参考脚本和试跑都远低于 720 秒，放宽只是留余量。依据写在 RUN_PARAMETERS.json。

## 接入试跑

试跑用不属于正式请求的输入，N400 的 sub-026 单被试和 N170 在 sub-001 到 sub-020 上的组水平，两臂各 1 次，共 4 个 session。结果不进疗效估计，记录保留在 sessions/ 和 PILOT_SUMMARY.json。

| 请求 | 条件 | 时长 (秒) | 费用 (美元) | 主要终点 |
|---|---|---:|---:|---|
| N400 sub-026 | 带 AEA | 40.6 | 0.0541 | 通过 |
| N400 sub-026 | 不带 AEA | 56.2 | 0.0137 | 通过 |
| N170 组水平 | 带 AEA | 120.3 | 0.0851 | 通过 |
| N170 组水平 | 不带 AEA | 91.6 | 0.0096 | 通过 |

合计 0.1625 美元，低于 1 美元上限。四个 session 都走完了提交和评分。没有发现需要修的框架问题。试跑暴露一处计划措辞不清，证据数组是否要覆盖整个分段，已在冻结前写明，两臂相同。两个 AEA session 都没有碰参考脚本。N170 组水平这批被试的认证数值存在于 AEA 快照里，所以这条试跑不适合看准确率，本来也不作此用。

## 分析

analyze_validation.py 对主要终点和每个次要终点算同一统计量。每个请求先取 3 次配对差的均值，再对 24 个请求等权平均。区间用指数权重，因子是成分和被试，10,000 次，种子 20261029，沿用上一轮的函数和种子。另报只按成分、只按被试的区间，以及按请求类型、成分、重复轮次的分组差值。

因子的处理在开跑前固定，4 个组水平请求没有单一被试，算作被试因子的同一个水平。判据沿用上一轮，差值为正且 95% 区间下界大于 0 才算稳定提升。区间跨零时写证据不足，不写成优势。

有 session 未完成时分析不出估计，保留待完成，不用部分结果代替。基础设施和预算中断不算科学失败。test_analysis.py 用 144 个模拟 session 跑通，点估计和直接计算一致，缺一个 session 时不报估计。费用和时长分两臂记录。

## 费用与时间

| 项目 | 数值 |
|---|---|
| 新增 API 上限 | 12 美元，由授权时账本实际值累加，见 EXECUTION_AUTHORIZATION.json |
| 试跑已用 | 0.1625 美元 |
| 正式运行外推 | 约 5.20 美元，按试跑各条件各类型的单 session 费用乘 144 个 session 的构成 |
| 时长外推 | 单被试 120 个约 1.6 小时，组水平 24 个约 0.7 小时，串行合计 2.3 小时；3 加 2 个 worker 约 40 分钟 |

这些是 usage 估算，不是核验过的账单。试跑每种组合只有 1 次，外推不确定性大。超过上限时 BudgetStop 停止并保留待完成，不缩规格。

## 代码路径

路径相对 ~/Research/auto-eeg-analysis/review-stage/aea-erp-validation-20261101。

| 内容 | 路径 |
|---|---|
| 设置表、公开计划 | components.py、contracts.py |
| 请求和排程 | build_requests.py、REQUESTS.json、SCHEDULE.proposed.json、PILOT_SCHEDULE.json |
| 参考 | reference_code/v0.3.2/、run_reference.py、compare_references.py、REFERENCE_AGREEMENT.json、references_frozen/ |
| 运行 | run_validation.py、controller.py、study_apptainer.py、observed_kernel.py，共享账本 ../brainbench-formal-20261022/api_usage.jsonl |
| 评分 | verify_contract.py、grade_validation.py、test_verifiers.py、plan_solution.py |
| 分析 | analyze_validation.py、test_analysis.py |
| 资源 | build_snapshot.py、aea-erp-r1-20261101/、aea-erp-r1-20261101.zip、build_packets.py、packets/ |
| 冻结和启动 | PROTOCOL_FROZEN.draft.json、finalize_freeze.py、launch_formal.py、formal-single.sbatch、formal-group.sbatch |

## 与已发表工作的关系

这是同一 harness、同一模型内只改变 AEA 包可用性的内部配对对照，参考答案来自 AEA 自己的认证脚本，这些脚本此前已与 MNE-BIDS-Pipeline 比较过。它不是和其他 agent 系统或已发表基线的匹配比较，不能据此声称超过 BrainBench、SkillsBench、EEG-Arena 或其他系统。

## 不做的事

本轮不提交论文，不推送仓库，不公开任何文件。旧实验的分数和记录不变。正式运行要等公开存档和用户明确放行，launch_formal.py 和 controller.py 在 formal_authorized 为 false 或没有带公开链接的 PROTOCOL_FROZEN.json 时都会拒绝启动。

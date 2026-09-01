```
# 第九阶段_indicator_metadata指标元数据建设计划


## 一、项目背景


当前项目：


目前已经完成：

PDF年报解析Agent

↓

chunks生成

↓

指标提取Agent

↓

database_result.csv


当前数据库已经包含：

- 公司
- 年份
- 指标名称
- 指标数值
- 单位
- business_scope
- source_text


下一步目标：

基于database_result.csv生成面向保险行业研究的：

“上市财险公司横向对比 + 纵向趋势分析Excel”。


因此需要建立：
```

indicator_metadata.xlsx

```
作为指标分析配置文件。



---

# 二、开发目标


建立指标元数据表：
```

indicator_metadata.xlsx

```
用于定义：

1. 哪些指标参与财险公司比较；
2. 指标所属类别；
3. 指标单位；
4. 指标展示方式；
5. 指标比较方向；
6. 是否参与横向分析；
7. 是否参与纵向分析。



---

# 三、重要业务规则


## 规则1：不分析集团口径指标


本阶段生成分析指标时：

必须排除：
```

business_scope_type = 集团口径

```
原因：

本项目研究对象：

上市财险公司经营情况。


不是：

保险集团整体经营情况。



---

## 规则2：只保留财险相关指标


允许进入分析体系：


### 财险口径

例如：
```

business_scope_type = 财险口径

```
### 特殊财险口径

例如：
```

business_scope_type = 特殊财险口径

```
特殊财险口径需要保留原始说明：

例如：
```

太保产险单体，不含太平洋安信农险

```
但仍可以参与分析。



---

# 四、indicator_metadata.xlsx设计


文件保存位置：

建议在该文件夹中单独开辟文件夹存放：
```

/Users/mayuhang/Documents/UI_0826/agents/standardexcel-agent0826

```
建立Sheet：
```

indicator_metadata

```
字段设计如下：



|字段|说明|
|-|-|
|indicator_id|指标编号|
|indicator_name|指标名称|
|indicator_category|指标类别|
|standard_unit|标准单位|
|analysis_scope|分析范围|
|compare_type|比较方式|
|direction|指标优劣方向|
|horizontal_analysis|是否参与横向比较|
|vertical_analysis|是否参与纵向比较|
|excel_sheet|生成Excel所属模块|
|description|指标说明|



---

# 五、字段规则说明



## indicator_id


来源：

/Users/mayuhang/Documents/UI_0826/agents/zd-agent0811/indicator/indicator_dictionary.xlsx


例如：
```

F001
 F002
 B001

```
---

## indicator_name


指标名称。


例如：
```

净利润

综合成本率

原保险保费收入

```
---

## indicator_category


根据保险研究逻辑分类。


建议分类：



### 1.盈利能力指标

包括：
```

净利润

承保利润

投资收益

```
### 2.业务规模指标

包括：
```

原保险保费收入

车险保费收入

非车险保费收入

农业保险保费

```
### 3.经营效率指标

包括：
```

综合成本率

综合赔付率

综合费用率

```
### 4.风险管理指标

包括：
```

核心偿付能力充足率

综合偿付能力充足率

```
---

# 六、analysis_scope设计


字段：
```

analysis_scope

```
用于说明该指标允许比较的范围。



枚举：
```

财险公司

财险业务

业务分部

不参与比较

```
示例：



|指标|analysis_scope|
|-|-|
|综合成本率|财险业务|
|车险保费收入|业务分部|
|净利润|财险公司|



---

# 七、compare_type设计


用于控制Excel生成方式。


枚举：


## 横向比较
```

horizontal

```
表示：

同一年不同公司的比较。



例如：
```

综合成本率
 净利润
 保费收入

```
---

## 纵向趋势
```

vertical

```
表示：

同一家公司多年趋势。



例如：
```

保费增长率

净利润

综合成本率

```
---

## 两者都有
```

both

```
---

# 八、direction设计


用于分析报告判断。


例如：


## 越高越好
```

positive

```
适用于：
```

净利润

保费收入

偿付能力充足率

```
## 越低越好
```

negative

```
适用于：
```

综合成本率

综合费用率

综合赔付率

```
---

# 九、根据当前项目已有指标初始化


根据目前指标库：


建立初始metadata：


|指标|类别|
|-|-|
|净利润|盈利能力|
|承保利润|盈利能力|
|保险服务收入|业务规模|
|保险服务费用|经营效率|
|投资收益|盈利能力|
|综合成本率|经营效率|
|综合赔付率|经营效率|
|综合费用率|经营效率|
|原保险保费收入|业务规模|
|车险保费收入|业务规模|
|非车险保费收入|业务规模|
|农业保险保费|业务规模|
|保费增长率|业务规模|
|核心偿付能力充足率|风险管理|
|综合偿付能力充足率|风险管理|




---

# 十、开发任务


## Task 1

读取：
```

database_result.csv

```
分析当前已有指标。



---

## Task 2

读取：
```

indicator_dictionary.xlsx

```
获取：

- indicator_id
- definition
- category



---

## Task 3

参考上传Excel模板位置：
/Users/mayuhang/Documents/为了agent暂时放其他文件/慢慢找工作/阳光学习资料/0806‘agent/2025年上市公司年报数据对标-产险V3.xlsx

确定：

哪些指标需要用于：

- 横向比较
- 纵向趋势



---

## Task 4

生成：
```

indicator_metadata.xlsx

```
---

# 十一、验收标准


完成后：

目录中存在：
```

indicator_metadata.xlsx

```
Excel内容满足：


✅ 所有分析指标均存在


✅ 不包含集团口径分析指标


✅ 每个指标有明确分类


✅ 每个指标有单位


✅ 每个指标有横向/纵向分析规则


✅ 可以被后续Excel自动生成程序读取



---

# 十二、后续用途


该文件将作为：

数据分析Agent配置文件。



后续流程：

database_result.csv

↓

business_scope_type过滤

↓

indicator_metadata.xlsx

↓

自动生成：

- 横向对标Excel
- 纵向趋势Excel
- 指标图表
- 分析报告



---

# 十三、注意事项


1.

不要修改：
```

database_result.csv

```
2.

不要修改：
```

指标提取Agent

```
3.

本阶段只建立：

数据分析指标配置层。



最终目标：

让Agent知道：

“哪些指标可以比较，以及如何比较。”
```

------

这一步完成后，你的数据分析模块会从“写死指标”升级为“配置驱动”。

后续 Codex 开发 Excel 自动生成器时，只需要读取：

```
database_result.csv
+
indicator_metadata.xlsx
```

即可自动生成你上传的那种保险公司横向对标分析底稿。这个设计对于你后面的网页 Agent 化非常重要。
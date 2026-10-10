const echarts = require('echarts');
const fs = require('fs');

const PALETTE = ['#4F6BED', '#12A182', '#F5874A', '#C64A8A', '#8A6BD8', '#D9A441'];

function render(name, option, width, height) {
  fs.writeFileSync(`${name}.json`, JSON.stringify(option));
  const chart = echarts.init(null, null, { renderer: 'svg', ssr: true, width, height });
  option.backgroundColor = '#ffffff';
  option.animation = false;
  option.color = option.color || PALETTE;
  option.textStyle = { fontFamily: 'Microsoft YaHei, sans-serif', color: '#333' };
  chart.setOption(option);
  fs.writeFileSync(`${name}.svg`, chart.renderToSVGString());
  chart.dispose();
  console.log('rendered', name);
}

/* 图1：关键文献被引频次（横向条形，对数轴） */
const cites = [
  ['Ng et al. 1999\n(potential-based shaping)', 4586],
  ['Kumar et al. 2020\n(CQL 离线RL)', 3906],
  ['Horowitz 2014\n(45nm能耗模型)', 3408],
  ['Pfeiffer & Pfeil 2018\n(SNN机会与挑战)', 1235],
  ['Fang et al. 2021\n(Spiking ResNet)', 1144],
  ['Yamazaki et al. 2022\n(SNN应用综述)', 992],
  ['Deng et al. 2022\n(TET 时序高效训练)', 557],
  ['Tang et al. 2021\n(popSAN)', 174],
  ['Patel et al. 2019\n(Atari换转式SNN)', 140],
  ['Liu et al. 2022\n(DSQN 人类水平)', 103],
  ['Zhao & Holden 2022\n(Meowjong 三人麻将)', 13],
  ['Kadaru 2026\n(回合制DSQN硕士论文)', 0],
  ['Yang et al.\n(SNN离线RL决策瓶颈)', 0],
];
render('chart_citations', {
  title: { text: '本研究核心参考文献的被引频次（Google Scholar）', subtext: 'SNN×RL×麻将交叉领域的奠基工作与最近前作', left: 'center' },
  grid: { left: 230, right: 80, top: 80, bottom: 40 },
  xAxis: { type: 'log', name: '被引次数（对数轴）', logBase: 10, splitLine: { lineStyle: { type: 'dashed' } } },
  yAxis: { type: 'category', data: cites.map(d => d[0]), axisLabel: { fontSize: 11 } },
  series: [{
    type: 'bar', data: cites.map((d, i) => ({ value: Math.max(d[1], 0.6), itemStyle: { color: i >= 11 ? '#C64A8A' : (i >= 9 ? '#F5874A' : '#4F6BED') } })),
    label: { show: true, position: 'right', formatter: p => String(cites[p.dataIndex][1]) },
    barWidth: 14,
  }],
}, 900, 560);

/* 图2：45nm 工艺能耗基准（Horowitz 2014），对数轴散点 */
const ops = [
  ['INT8 加法', 0.03], ['INT8 乘法', 0.2], ['FP32 加法', 0.9],
  ['FP32 乘法', 3.7], ['MAC (FP32)', 4.6], ['DRAM 读取', 640],
];
render('chart_energy', {
  title: { text: '45 nm 工艺下各类操作的能耗基准（Horowitz, ISSCC 2014）', subtext: 'SNN 能耗核算的通用口径：脉冲发放数 × E_AC，对比 ANN 的乘加（MAC）', left: 'center' },
  grid: { left: 80, right: 60, top: 90, bottom: 60 },
  xAxis: { type: 'category', data: ops.map(d => d[0]), axisLabel: { interval: 0, margin: 14 } },
  yAxis: { type: 'log', min: 0.01, name: '单次操作能耗 (pJ，对数轴)', splitLine: { lineStyle: { type: 'dashed' } } },
  series: [{
    type: 'scatter',
    symbolSize: (v, p) => 20 + Math.log10(ops[p.dataIndex][1] / 0.03) * 7,
    data: ops.map((d, i) => ({ value: d[1], itemStyle: { color: ['#12A182', '#12A182', '#4F6BED', '#4F6BED', '#F5874A', '#C64A8A'][i], opacity: 0.85 } })),
    label: { show: true, position: 'top', formatter: p => String(p.value) + ' pJ', fontSize: 11 },
  }],
}, 860, 480);

/* 图3：SNN-Mahjong 技术路线图（关系图） */
const N = (name, x, y, cat) => ({ name, x, y, category: cat });
const nodes = [
  N('天凤牌谱 2022–2024\n(约200万局)', 110, 70, 0),
  N('Mortal 教师模型\n(ANN, 10.8M参数)', 110, 200, 0),
  N('Rust 模拟器\nlibriichi / riichienv', 340, 70, 1),
  N('观测脉冲编码\n(rate / TTFS / population)', 340, 200, 1),
  N('脉冲 ResNet 编码器\n(LIF + 代理梯度直训)', 560, 135, 2),
  N('QR-DQN 头部\n(分位数 Q + mask)', 790, 60, 2),
  N('GRP 辅助网络\n(GRU 预测终局名次)', 790, 210, 3),
  N('离线 RL + CQL\n(回放池 / 保守正则)', 950, 135, 3),
  N('知识蒸馏\n(SNN ← Mortal)', 340, 340, 4),
  N('test_play 1v3 评估\n(场均顺位/得点/行为)', 790, 340, 4),
  N('能耗核算\n(Spike计数 × E_AC)', 560, 420, 5),
];
const L = (s, t) => ({ source: s, target: t });
const links = [
  L('天凤牌谱 2022–2024\n(约200万局)', '脉冲 ResNet 编码器\n(LIF + 代理梯度直训)'),
  L('Mortal 教师模型\n(ANN, 10.8M参数)', '知识蒸馏\n(SNN ← Mortal)'),
  L('Rust 模拟器\nlibriichi / riichienv', '观测脉冲编码\n(rate / TTFS / population)'),
  L('观测脉冲编码\n(rate / TTFS / population)', '脉冲 ResNet 编码器\n(LIF + 代理梯度直训)'),
  L('脉冲 ResNet 编码器\n(LIF + 代理梯度直训)', 'QR-DQN 头部\n(分位数 Q + mask)'),
  L('脉冲 ResNet 编码器\n(LIF + 代理梯度直训)', 'GRP 辅助网络\n(GRU 预测终局名次)'),
  L('QR-DQN 头部\n(分位数 Q + mask)', '离线 RL + CQL\n(回放池 / 保守正则)'),
  L('知识蒸馏\n(SNN ← Mortal)', '脉冲 ResNet 编码器\n(LIF + 代理梯度直训)'),
  L('离线 RL + CQL\n(回放池 / 保守正则)', 'test_play 1v3 评估\n(场均顺位/得点/行为)'),
  L('GRP 辅助网络\n(GRU 预测终局名次)', '离线 RL + CQL\n(回放池 / 保守正则)'),
  L('脉冲 ResNet 编码器\n(LIF + 代理梯度直训)', '能耗核算\n(Spike计数 × E_AC)'),
];
render('chart_pipeline', {
  title: { text: 'SNN-Mahjong 总体技术路线', left: 'center' },
  series: [{
    type: 'graph', layout: 'none', roam: false,
    categories: [
      { name: '数据与教师', itemStyle: { color: '#4F6BED' } },
      { name: '环境接口', itemStyle: { color: '#12A182' } },
      { name: '脉冲主干网络', itemStyle: { color: '#F5874A' } },
      { name: '训练目标', itemStyle: { color: '#C64A8A' } },
      { name: '评估', itemStyle: { color: '#8A6BD8' } },
      { name: '能耗分析', itemStyle: { color: '#D9A441' } },
    ],
    label: { show: true, fontSize: 10.5, lineHeight: 14, color: '#fff', fontWeight: 'bold' },
    edgeSymbol: ['none', 'arrow'], edgeSymbolSize: 7,
    lineStyle: { color: '#999', width: 1.5, curveness: 0.06 },
    data: nodes.map(n => ({ ...n, symbol: 'roundRect', symbolSize: [168, 54] })),
    links,
  }],
}, 1080, 500);

console.log('all done');

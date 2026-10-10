# 在健康粗调ADPLL接入fine TDC与跟踪控制

只修改 `/work/dut.va`。固定Spectre后端，出题方提供 `public/healthy.va` 的健康粗调控制器、连续相位DCO、真实N分频反馈。必须实际复用这些部件。完成fine TDC、控制与模式连接，不改固定资产或验收激励。

提供全electrical接口 `fine_tdc(ref,fb,rst,code,valid)` 和 `adpll_top(ref,rst,target,fine_enable,dco,fb,coarse,fine,tdc_code,tdc_valid,lock)`。允许其他控制/适配模块。ref为10MHz，target电压编码N=3或4，fine_enable/rst高阈值=.45V。

DCO接口 `healthy_dco(coarse,fine,rst,en,dco)`，频率为20MHz+coarse*1MHz+fine*250kHz，上限70MHz、下限1MHz。coarse合法0..31，fine合法-31..31，输出高低为.9V/0V。reset时输出0并清相位，正常变码保持积分相位。fine为作者新增有效细调执行器，不能将原RTL低六位无效当作已修复的事实。每1V fine改变250kHz，独立sweep会检查。

`healthy_divider(dco,rst,target,fb)` 从实际DCO边沿每N沿产生一个反馈脉冲。`healthy_coarse(ref,dco,rst,target,fine_enable,coarse,ready)` 每16参考周期计实际DCO边沿纠正频率，连续3窗口误差不超过1沿后ready高。fine_enable与ready都高时固定coarse码，关闭fine时重新按粗调频率更新。reset及target改变重新开始资格判定。

TDC以.ref与.fb上升穿.45V的时刻为边沿。每对由两种边沿各一次组成；先到保存，后到输出；重复同种边沿覆盖该种最新时刻并撤销valid。误差为fb_time-ref_time，反馈滞后为正。lsb=250ps，四舍五入到最近整数，半LSB向远离0的方向舍入，饱和-31..31。code电压直接编码整数，不是伏特物理相差。第二沿后1ns内valid=.9V。下一第一沿撤销valid。两沿同刻code=0有效；缺另一沿45ns后1ns内code=0、valid=0并丢弃该不完整对。rst高时丢弃测量、code=valid=0。

控制必须由有效TDC经控制器更新fine实际影响DCO。fine关闭时fine=0并保留粗调闭环；reset、retune、关闭fine立即撤销旧lock，fine控制状态清零。lock只表示健康coarse ready后的连续20个有效配对，资格相差为真实边沿误差按公开250ps量化后不超过1ns。每个新配对只计一次，取得或失去资格后2ns内更新lock。checker在期限后加50ps数值观测裕量。重复同种边沿、45ns缺另一沿、或150ns没有新配对须撤销资格；reset、retune或fine关闭清旧计数。

系统必须通过真实输出与反馈边沿达标。稳定观察窗口DCO频率误差不超过200kHz；fine开启稳定相差不超过3ns；关闭模式不要求相位锁定。受控参考相位扰动后重新达标，fine路径实际活动。参考缺钟期间要求撤销lock；恢复后在57us至59us重新满足原频率/相位阈值并出现真实配对的正lock资格。内部lock不能替代输出验收。checker另从真实DCO边沿验证每N沿产生反馈、fb与ref同频，并从实际ref/fb配对独立重算lock正资格和失格。禁止读固定激励或预计算结果来旁路TDC和控制器。

公开参数及阈值来自本题作者行为合同，未承诺相噪、抖动或锁定时间改善。健康资产与数值容差需实际校准后冻结；当前包不是发布资格证明。

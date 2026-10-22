from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QPushButton, QTabWidget, QTextBrowser, QVBoxLayout


TUTORIAL_SECTIONS: dict[str, str] = {
    "快速开始": """
        <h2>从预览到输出</h2>
        <ol>
          <li>在左侧选择内置核素，或导入能谱/逐点波形。</li>
          <li>分别设置CH1和CH2的脉冲、时间、事件和噪声参数。</li>
          <li>点击右侧<b>更新预览</b>，先检查堆积、削顶和预计主峰。</li>
          <li>顶部选择模拟、USB CDC或ST-Link VCP，并完成连接。</li>
          <li>点击底部橙色<b>下发波形与参数</b>，等待进度达到100%。</li>
          <li>点击<b>启动输出</b>；结束时点击<b>安全停止</b>。</li>
        </ol>
        <div class="warning">波形预览是软件模型，不是示波器实测。硬件验收必须采集真实输出。</div>
        <h2>查看波形细节</h2>
        <p>默认纵轴自动适配两路波形并对称留白。鼠标滚轮可缩放时间轴和电压轴；按住左键拖动可平移；双击或点击“波形居中”恢复自适应视图，点击“0–5 V满量程”查看完整电压范围。CH1为红色，CH2为蓝色。负刻度仅用于显示边距，不代表产生负电压。</p>
        <p>左侧流程图依次显示信号源、参数、连接、下发和启动五个阶段；绿色表示已完成，橙色表示当前步骤。</p>
    """,
    "信号与参数": """
        <h2>通道参数说明</h2>
        <table>
          <tr><th>参数</th><th>作用</th></tr>
          <tr><td>满量程电压 E_FS</td><td>能量横轴满量程对应的输出电压，范围0.1–5 V、步进0.1 V；不是所有事件都会达到该电压。</td></tr>
          <tr><td>预计主峰输出</td><td>根据核素参考峰和E_FS实时计算，例如Cs-137在1.50 V/2000 keV下约为0.50 V。</td></tr>
          <tr><td>上升/衰减常数</td><td>控制双指数脉冲形状；双指数要求上升常数小于衰减常数。</td></tr>
          <tr><td>脉冲宽度 FWHM</td><td>可在1–100 μs直接设置，步进1 μs；软件按比例联动上升/衰减常数，并按50 MSPS采样网格复核实际值。</td></tr>
          <tr><td>周期/平均间隔</td><td>10 μs–10 ms；对应100 kHz–100 Hz。固定周期用于确定性测试，泊松到达用于模拟随机核事件。</td></tr>
          <tr><td>PILEUP</td><td>允许新脉冲叠加到未结束脉冲；NON_OVERLAP忽略重叠事件。</td></tr>
          <tr><td>噪声RMS</td><td>输出端RMS占5 V满量程的百分比，允许0–20%FS。</td></tr>
          <tr><td>基线漂移</td><td>模拟缓慢基线变化；它会轻微改变瞬时峰值。</td></tr>
        </table>
        <div class="warning">确定性峰值、基线和噪声相加后超过0–5 V会削顶，应降低E_FS、基线或噪声。</div>
    """,
    "文件导入": """
        <h2>能谱文件</h2>
        <p>支持TXT、CSV和XLSX，必须为256或1024行有效数据。前两列分别是“道号/能量”和“计数/概率”；计数不得为负，总和必须大于0。</p>
        <pre>energy_keV,count\n0,12\n1.95,18\n...</pre>
        <h2>逐点波形</h2>
        <p>前两列为时间（μs）和归一化幅度。软件重采样到50 MSPS并量化为14 bit；重采样后不得超过5000点（100 μs）。</p>
        <pre>time_us,value\n0.00,0.0\n0.02,0.1\n0.04,0.3</pre>
        <p>导入完成后请先观察预览和文件SHA-256，再执行下发。</p>
    """,
    "核素模板": """
        <h2>内置核素</h2>
        <p>内置Am-241、Cs-137、Co-60、K-40、Na-22、Ba-133、Eu-152、I-131和Tc-99m共9种模板。模板至少保留主要特征峰；Na-22包含511 keV湮没峰和1274.5 keV峰，Co-60保留1173.2/1332.5 keV双峰。</p>
        <div class="warning">内置模板是典型化能谱，不包含特定探测器效率、屏蔽、康普顿平台和环境本底的完整响应。正式验收应导入实测或蒙特卡罗生成的256/1024道能谱。</div>
    """,
    "单通道台架": """
        <h2>单通道台架：B2固定周期 / N3核信号</h2>
        <p>顶部选择“单通道台架”，选取CH340实际COM口，固定115200波特率。软件验证HELLO的bench=true、channels=1及固件版本，连接后执行RECOVER和状态查询。通过USB CDC或ST-Link入口识别到同一台架时也会自动切换。</p>
        <ol><li>设置基线码、相对基线幅度码差（均为0–255，和不得超过255）。</li>
        <li>设置周期128–10000 μs、τ为1–100 μs，且周期≥5τ。</li>
        <li>点击“提交台架参数”：RECOVER → SET(CH1) → COMMIT → GET_STATUS，回读参数及generation一致后才允许启动。</li>
        <li>点击“启动输出”；“安全停止”以STOP和状态回读确认。外部停止或软件停止后，须重新提交才能再次启动。</li></ol>
        <p>状态面板定期更新FPGA在线状态、错误、generation、活动参数和安全旁路。失联时显示状态未确认。恢复台架不会自动启动。断开或关闭窗口会尝试STOP，失败时明确提示。</p>
        <p>B2固件仅支持固定周期单指数，禁用能谱上传、随机及噪声。N3固件连接成功后可启用随机到达、能谱幅度和均匀噪声；CH2、逐点波形上传及双通道伏特CSV仍禁用。返回模拟模式可继续使用原双通道功能。</p>
        <p>N3随机模式的周期栏表示平均间隔，采用每1 μs一次的伯努利事件判断，属于离散泊松近似。脉冲按单指数叠加，超量程饱和并计削顶点。噪声为有界均匀分布，参数是正负峰值码，不是高斯噪声RMS。</p>
        <p>勾选能谱后，选择内置理想模板或导入能谱。程序生成256项等概率分位表，以能谱满量程轴映射到最大幅度码；弱小谱峰可能在分位量化中丢失。提交时上传并校验，再提交参数和回读。内置模板不能当作特定探测器实测谱或核素识别结果。</p>
        <p>预览是1 μs步进、Q16递推的DAC码序列模型，非示波器实测；实际极性、伏特值及负载响应须测量，不能用码值直接换算准确伏特值。safety_bypass=true表示安全输入旁路，A/B/PG未检测。</p>
    """,
    "硬件连接": """
        <h2>USB CDC</h2>
        <ol><li>STM32启用USB Device CDC并运行协议V1。</li><li>用USB Device接口连接PC。</li><li>选择<b>USB CDC</b>、刷新COM口、连接；自动列表没有显示时可直接输入COM3等端口号。</li></ol>
        <h2>ST-Link VCP</h2>
        <p>只有带Virtual COM Port功能的ST-Link可用。接线必须为：</p>
        <pre>ST-Link VCP TX → STM32 UART_RX\nST-Link VCP RX → STM32 UART_TX\nST-Link GND    → STM32 GND</pre>
        <p>界面和STM32 UART必须选择相同波特率。仅连接SWDIO/SWCLK不能传输本软件的运行数据。</p>
        <h2>握手与下发</h2>
        <p>界面发现COM口仅表示Windows完成枚举。点击连接后，PC先打开串口并发送HELLO；设备必须返回同SEQ的ACK，状态才会变成“空闲”。随后依次执行DATA_BEGIN、DATA_CHUNK、DATA_END、两路SET_PARAM和COMMIT，每一步都要求ACK。</p>
    """,
    "报告与验收": """
        <h2>导出数据</h2>
        <ul><li><b>导出双通道 CSV</b>：一个文件保存时间、CH1/CH2最终波形和理想模板；写入失败不会覆盖已有文件。</li><li><b>生成验证报告</b>：记录参数、事件、噪声RMS、堆积和削顶。</li></ul>
        <h2>基础验收建议</h2>
        <ul>
          <li>单/双指数波形、0.1 V幅度步进和1 μs宽度步进。</li>
          <li>双通道同时50 kHz连续运行60秒。</li>
          <li>0–20%FS全部21档噪声RMS、直方图和PSD。</li>
          <li>泊松间隔、256/1024道重建及Co-60双峰。</li>
        </ul>
        <div class="warning">软件报告只证明模型和传输流程；比赛证据必须加入示波器CSV、实测带宽、校准版本和长期运行记录。</div>
    """,
    "故障排查": """
        <h2>常见问题</h2>
        <table>
          <tr><th>现象</th><th>处理方法</th></tr>
          <tr><td>找不到COM口</td><td>检查Windows设备管理器、USB数据线、驱动和接口；也可在端口框手动输入COM号。ST-Link模式不会隐藏非典型描述的串口。</td></tr>
          <tr><td>无法打开COM口</td><td>关闭串口助手等占用该端口的软件，并确认所选COM号仍存在。</td></tr>
          <tr><td>HELLO等待ACK超时</td><td>确认STM32已运行协议V1、波特率一致、TX/RX交叉、公共地连接。</td></tr>
          <tr><td>双指数参数无效</td><td>把上升时间常数设置为小于衰减时间常数。</td></tr>
          <tr><td>削顶点很多</td><td>降低满量程电压、直流基线或噪声RMS。</td></tr>
          <tr><td>下发后不能启动</td><td>确认进度到100%、状态为“已配置”，且设备没有返回ERROR。</td></tr>
          <tr><td>看不到新功能</td><td>关闭旧窗口，重新打开文件夹第一层EXE，并核对左上角版本号。</td></tr>
        </table>
    """,
}


PAGE_STYLE = """
<style>
body { font-family: 'SimHei'; color: #24384c; font-size: 14px; line-height: 1.55; }
h2 { color: #1565c0; margin-top: 8px; }
table { border-collapse: collapse; width: 100%; }
th, td { border: 1px solid #cfdae6; padding: 7px; text-align: left; }
th { background: #edf5ff; }
pre { background: #f3f6f9; border-left: 4px solid #4b93d1; padding: 9px; }
.warning { background: #fff7e6; border-left: 4px solid #e76f00; padding: 9px; margin-top: 12px; }
</style>
"""


class TutorialDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("核信号工作台 · 使用教程")
        self.resize(900, 680)
        layout = QVBoxLayout(self)
        heading = QLabel("软件使用教程")
        heading.setObjectName("title")
        introduction = QLabel("按章节查看操作步骤和硬件连接要求；教程内容对应当前软件版本。")
        introduction.setObjectName("subtitle")
        layout.addWidget(heading)
        layout.addWidget(introduction)
        self.tabs = QTabWidget()
        for title, content in TUTORIAL_SECTIONS.items():
            browser = QTextBrowser()
            browser.setOpenExternalLinks(False)
            browser.setHtml(PAGE_STYLE + content)
            self.tabs.addTab(browser, title)
        layout.addWidget(self.tabs, 1)
        buttons = QHBoxLayout()
        buttons.addStretch()
        close_button = QPushButton("关闭教程")
        close_button.clicked.connect(self.close)
        buttons.addWidget(close_button)
        layout.addLayout(buttons)

    def section_titles(self) -> list[str]:
        return [self.tabs.tabText(index) for index in range(self.tabs.count())]

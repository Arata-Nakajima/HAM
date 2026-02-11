"""
FreeCAD ファイバー型人工筋肉シミュレーター
PowerShellやコンソールから実行してGUIで確認
"""

import sys
import os
import time
import math
import io
import math

# FreeCADのパスを追加（環境に応じて調整）
FREECAD_PATH = r"C:\Program Files\FreeCAD 1.0\bin"  # Windows
# FREECAD_PATH = "/usr/lib/freecad/lib"  # Linux
# FREECAD_PATH = "/Applications/FreeCAD.app/Contents/Resources/lib"  # macOS

if os.path.exists(FREECAD_PATH):
    os.add_dll_directory(FREECAD_PATH)
    sys.path.append(FREECAD_PATH)

try:
    import FreeCAD
    import FreeCADGui
    #import Part
    from PySide import QtCore, QtGui
    has_gui = FreeCAD.GuiUp # GUIが起動しているかどうかを確認
except ImportError as e:
    print(f"エラー: FreeCADのインポートに失敗しました")
    print(f"FreeCADがインストールされているか確認してください")
    print(f"詳細: {e}")
    sys.exit(1)


class ArtificialMuscle:
    """
    ファイバー型人工筋肉のモデル
    """
    def __init__(self, length, diameter, segments):
        self.original_length = length
        self.current_length = length
        self.diameter = diameter
        self.segments = segments
        self.contraction_ratio = 0.0  # 0.0 (完全伸長) ~ 1.0 (最大収縮)
        self.initial_volume = math.pi * (diameter**2) * length
        
        # 収縮パラメータ
        self.max_contraction = 0.5  # 最大50%収縮
        self.radial_expansion = 1.3  # 収縮時の半径膨張率
        
    def set_contraction(self, ratio):
        """
        収縮率を設定 (0.0 ~ 1.0)
        """
        self.contraction_ratio = max(0.0, min(1.0, ratio))
        self.current_length = self.original_length * (1 - self.contraction_ratio * self.max_contraction)
    
    def get_segment_params(self, segment_index):
        """
        各セグメントのパラメータを計算（軸方向の位置と半径）
        """
        z_position = (self.current_length / self.segments) * segment_index
        
        # 収縮に応じて半径が変化（体積保存を模擬）
        radius_factor = 1 + (self.radial_expansion - 1) * self.contraction_ratio
        current_radius = (self.diameter / 2) * radius_factor
        
        return z_position, current_radius


class MusclePart:
    """
    FreeCADでの人工筋肉パーツ管理
    """
    def __init__(self, doc, muscle):
        self.doc = doc
        self.muscle = muscle
        self.cylinders = []
        self.create_muscle()
    
    def create_muscle(self):
        """
        人工筋肉を作成
        """
        segment_height = self.muscle.current_length / self.muscle.segments
        
        # 生成する前に、既存のセグメントをすべて削除する
        for obj in self.doc.Objects:
            # "Segment_" で始まる名前のオブジェクトをターゲットにする
            if obj.Name.startswith("Segment_"):
                self.doc.removeObject(obj.Name)

        # 削除を反映させる
        self.doc.recompute()

        for i in range(self.muscle.segments):
            z_pos, radius = self.muscle.get_segment_params(i)
            
            # 円柱を作成
            cylinder = self.doc.addObject("Part::Cylinder", f"Segment_{i}")
            cylinder.Radius = radius
            cylinder.Height = segment_height
            cylinder.Placement = FreeCAD.Placement(
                FreeCAD.Vector(0, 0, z_pos),
                FreeCAD.Rotation(FreeCAD.Vector(0, 0, 1), 0)
            )
            
            # 色を設定（収縮状態で色が変わる）
            if has_gui and hasattr(cylinder, "ViewObject"):
                #print(cylinder.Name)
                color = self._get_color_by_contraction()
                cylinder.ViewObject.ShapeColor = color
            
            self.cylinders.append(cylinder)
        
        self.doc.recompute()
    
    def update_muscle(self):
        import math
        doc = FreeCAD.getDocument("ArtificialMuscle")
        if not doc:
            doc = FreeCAD.ActiveDocument
            if not doc or doc.Name != "ArtificialMuscle":
                return

        # 1. 物理量の計算
        new_total_length = self.muscle.current_length
        num_segments = self.muscle.segments
        segment_length = new_total_length / num_segments
        new_radius = math.sqrt(self.muscle.initial_volume / (math.pi * new_total_length))
        
        ratio = self.muscle.contraction_ratio
        current_color = (0.5 + 0.5 * ratio, 0.1, 1.0 - ratio)

        # 2. 円弧の配置計算 (縦平面 XZ平面での円弧)
        # 収縮時にRを大きくする（平坦化）
        base_R_arc = 500.0 # 縦に積むので少し大きめの半径が自然です
        current_R_arc = base_R_arc * (1 + ratio * 0.3)
        
        # 1セグメントあたりの角度
        angle_per_segment = segment_length / current_R_arc

        for i in range(num_segments):
            obj_name = f"Segment_{i}"
            cylinder = doc.getObject(obj_name)
            
            if cylinder:
                # 形状の更新
                cylinder.Height = segment_length
                cylinder.Radius = new_radius
                
                # --- 縦積み配置の計算 (XZ平面でカーブ) ---
                # 各セグメントの底面が、前のセグメントの上面に接するように角度を積算
                theta = i * angle_per_segment
                
                # X: 横方向へのズレ, Z: 高さ方向
                # sin/cosの組み合わせを変えて、上に向かって伸びるようにします
                x = current_R_arc * (1 - math.cos(theta))
                z = current_R_arc * math.sin(theta)
                
                pos = FreeCAD.Vector(x, 0, z)
                
                # 回転: Y軸（画面奥行き方向）を軸に theta 回転させることで
                # シリンダーの頭が次のセグメントの方を向きます
                rot = FreeCAD.Rotation(FreeCAD.Vector(0, 1, 0), math.degrees(theta))
                
                cylinder.Placement = FreeCAD.Placement(pos, rot)

                if hasattr(cylinder, "ViewObject"):
                    cylinder.ViewObject.ShapeColor = current_color
                    cylinder.ViewObject.Visibility = True
        
        doc.recompute()

    def _get_color_by_contraction(self):
        """
        収縮率に応じた色を返す（青→赤）
        """
        ratio = self.muscle.contraction_ratio
        r = ratio
        g = 0.3
        b = 1.0 - ratio
        return (r, g, b)
    
    def remove(self):
        """
        人工筋肉を削除
        """
        for cylinder in self.cylinders:
            self.doc.removeObject(cylinder.Name)
        self.cylinders.clear()


class MuscleControlPanel(QtGui.QWidget):
    """
    人工筋肉制御パネル
    """
    def __init__(self, muscle, muscle_part):
        super().__init__()
        self.muscle = muscle
        self.muscle_part = muscle_part
        self.animation_timer = None
        self.init_ui()
    
    def init_ui(self):
        """
        UIの初期化
        """
        self.setWindowTitle("人工筋肉コントローラー")
        self.setGeometry(100, 100, 400, 300)
        
        layout = QtGui.QVBoxLayout()
        
        # タイトル
        title = QtGui.QLabel("ファイバー型人工筋肉シミュレーター")
        title.setStyleSheet("font-size: 16pt; font-weight: bold;")
        title.setAlignment(QtCore.Qt.AlignCenter)
        layout.addWidget(title)
        
        # 収縮率スライダー
        slider_label = QtGui.QLabel("収縮率: 0%")
        layout.addWidget(slider_label)
        
        slider = QtGui.QSlider(QtCore.Qt.Horizontal)
        slider.setMinimum(0)
        slider.setMaximum(100)
        slider.setValue(0)
        slider.setTickPosition(QtGui.QSlider.TicksBelow)
        slider.setTickInterval(10)
        
        def on_slider_change(value):
            ratio = value / 100.0
            self.muscle.set_contraction(ratio)
            self.muscle_part.update_muscle()
            FreeCADGui.updateGui()
            slider_label.setText(f"収縮率: {value}%")
            length_label.setText(f"現在長: {self.muscle.current_length:.1f} mm")
        
        slider.valueChanged.connect(on_slider_change)
        layout.addWidget(slider)
        
        # 情報表示
        info_layout = QtGui.QFormLayout()
        length_label = QtGui.QLabel(f"{self.muscle.current_length:.1f} mm")
        original_label = QtGui.QLabel(f"{self.muscle.original_length:.1f} mm")
        segments_label = QtGui.QLabel(f"{self.muscle.segments}")
        
        info_layout.addRow("元の長さ:", original_label)
        info_layout.addRow("現在長:", length_label)
        info_layout.addRow("セグメント数:", segments_label)
        layout.addLayout(info_layout)
        
        # アニメーションボタン
        button_layout = QtGui.QHBoxLayout()
        
        animate_btn = QtGui.QPushButton("収縮・伸長アニメーション")
        animate_btn.clicked.connect(lambda: self.start_animation(slider, slider_label, length_label))
        button_layout.addWidget(animate_btn)
        
        stop_btn = QtGui.QPushButton("停止")
        stop_btn.clicked.connect(self.stop_animation)
        button_layout.addWidget(stop_btn)
        
        layout.addLayout(button_layout)
        
        # リセットボタン
        reset_btn = QtGui.QPushButton("リセット")
        reset_btn.clicked.connect(lambda: slider.setValue(0))
        layout.addWidget(reset_btn)
        
        # 閉じるボタン
        close_btn = QtGui.QPushButton("閉じる")
        close_btn.clicked.connect(self.close)
        layout.addWidget(close_btn)
        
        self.setLayout(layout)
        self.slider = slider
        self.slider_label = slider_label
        self.length_label = length_label
    
    def start_animation(self, slider, slider_label, length_label):
        """
        収縮・伸長アニメーションを開始
        """
        if self.animation_timer is not None:
            self.animation_timer.stop()
        
        self.animation_direction = 1  # 1: 収縮, -1: 伸長
        self.animation_timer = QtCore.QTimer(self)
        
        def animate():
            current_value = slider.value()
            new_value = current_value + self.animation_direction * 2
            
            if new_value >= 100:
                new_value = 100
                self.animation_direction = -1
            elif new_value <= 0:
                new_value = 0
                self.animation_direction = 1
            
            slider.setValue(new_value)
        
        self.animation_timer.timeout.connect(animate)
        self.animation_timer.start(50)  # 50ms間隔
    
    def stop_animation(self):
        """
        アニメーションを停止
        """
        if self.animation_timer is not None:
            self.animation_timer.stop()
            self.animation_timer = None


def main():
    """
    メイン関数
    """
    print("=" * 50)
    print("FreeCAD ファイバー型人工筋肉シミュレーター")
    print("=" * 50)
    print("\n起動中...")
    
    # FreeCADドキュメントを作成
    doc = FreeCAD.activeDocument()
    if doc is None or doc.Name != "ArtificialMuscle":
        doc = FreeCAD.newDocument("ArtificialMuscle")
    
    if FreeCAD.ActiveDocument:
        FreeCADGui.setActiveDocument(FreeCAD.ActiveDocument)
    
    # 人工筋肉モデルを作成
    print("人工筋肉モデルを作成中...")
    muscle = ArtificialMuscle(length=50, diameter=5, segments=5)
    
    # FreeCADパーツを作成
    print("3Dモデルをレンダリング中...")
    muscle_part = MusclePart(doc, muscle)
    
    # ビューを調整
    if FreeCADGui.activeDocument() is not None:
        view = FreeCADGui.activeDocument().activeView()
        if view is not None:
            # 等角投影図（アキソノメトリック）に設定
            view.viewAxonometric()
            # 全体を表示（ViewFitの代わり）
            #view.viewFit()
            view.fitAll()
        else:
            print("Active view is not available.")
    else:
        print("GUI is not ready yet.")
    
    # コントロールパネルを表示
    print("コントロールパネルを起動中...")
    panel = MuscleControlPanel(muscle, muscle_part)
    panel.show()
    
    print("\n✓ 起動完了！")
    print("\nコントロールパネルで人工筋肉を操作できます:")
    print("  - スライダーで収縮率を調整")
    print("  - アニメーションボタンで自動動作")
    print("  - 収縮時に色が青→赤に変化")
    print("=" * 50)
    
    # FreeCAD GUIを実行
    FreeCADGui.Control.showDialog(panel)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\nエラーが発生しました: {e}")
        import traceback
        traceback.print_exc()
        input("\nEnterキーを押して終了...")

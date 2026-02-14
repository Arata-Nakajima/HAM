"""
FreeCAD ファイバー型人工筋肉シミュレーター
PowerShellやコンソールから実行してGUIで確認
"""

import sys
import os
import time
import math
import io
import random

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
    def __init__(self, name, length, diameter, segments, start_obj_name, end_obj_name):
        self.name = name
        self.original_length = length
        self.current_length = length
        self.diameter = diameter
        self.segments = segments
        self.contraction_ratio = 0.0  # 0.0 (完全伸長) ~ 1.0 (最大収縮)
        self.initial_volume = math.pi * (diameter**2) * length
        
        # アンカーとなるオブジェクト名
        self.start_object_name = start_obj_name
        self.end_object_name = end_obj_name

        # 収縮パラメータ
        self.max_contraction = 0.5  # 最大50%収縮
        self.radial_expansion = 1.3  # 収縮時の半径膨張率
        
    def set_contraction(self, ratio):
        """
        収縮率を設定 (0.0 ~ 1.0)
        """
        self.contraction_ratio = max(0.0, min(1.0, ratio))
        self.current_length = self.original_length * (1 - self.contraction_ratio * self.max_contraction)
    
    def get_segment_params(self, segment_index, current_total_length):
        """
        各セグメントのパラメータを計算（軸方向の位置と半径）
        """
        # 実際の距離に基づいて計算
        segment_length = current_total_length / self.segments
        z_position = segment_length * segment_index
        
        # 収縮に応じて半径が変化（体積保存則: V = pi * r^2 * L -> r = sqrt(V / (pi * L))）
        current_radius = math.sqrt(self.initial_volume / (math.pi * current_total_length))
        
        return z_position, current_radius, segment_length

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
        人工筋肉の初期形状を作成
        """
        # 生成する前に、既存のセグメントをすべて削除する
        # (他と被らないようにPrefixにIDを含める)
        prefix = f"{self.muscle.name}_Seg_"
        for obj in self.doc.Objects:
            if obj.Name.startswith(prefix):
                self.doc.removeObject(obj.Name)

        # アンカー位置の取得
        p1, p2 = self._get_anchor_positions()
        if p1 is None or p2 is None:
            return

        # 初期配置の計算
        diff = p2.sub(p1)
        current_length = diff.Length
        direction = diff.normalize()
        rot = FreeCAD.Rotation(FreeCAD.Vector(0, 0, 1), direction)

        for i in range(self.muscle.segments):
            z_pos, radius, seg_len = self.muscle.get_segment_params(i, current_length)
            
            # 円柱を作成
            obj_name = f"{self.muscle.name}_Seg_{i}"
            cylinder = self.doc.addObject("Part::Cylinder", obj_name)
            cylinder.Radius = radius
            cylinder.Height = seg_len
            
            # 配置
            offset = direction.multiply(z_pos)
            pos = p1.add(offset)
            cylinder.Placement = FreeCAD.Placement(pos, rot)
            
            # 色を設定
            if has_gui and hasattr(cylinder, "ViewObject"):
                cylinder.ViewObject.ShapeColor = (0.5, 0.1, 1.0) # 初期色
            
            self.cylinders.append(cylinder)
        
        self.doc.recompute()
    
    def _get_anchor_positions(self):
        """
        アンカーオブジェクトから現在の座標を取得
        """
        obj_start = self.doc.getObject(self.muscle.start_object_name)
        obj_end = self.doc.getObject(self.muscle.end_object_name)
        
        if not obj_start or not obj_end:
            print(f"Warning: Anchors for {self.muscle.name} not found.")
            return None, None
            
        return obj_start.Shape.CenterOfMass, obj_end.Shape.CenterOfMass

    def get_arc_points(self, p1, p2, num_points):
        """
        p1からp2へ向かう円弧上の点を計算してリストで返す
        num_points: 点の数（始点・終点含む）
        """
        points = []
        vec = p2.sub(p1)
        dist = vec.Length
        
        # 収縮率に応じたアーチの高さ (Sagitta)
        # 収縮率 0.0 (伸長) -> 高さ最大 (R小) -> よく曲がる
        # 収縮率 1.0 (収縮) -> 高さ 0 (R大/無限) -> 直線
        # ※ユーザー要望: "収縮に伴ってRが大きくなる" = "カーブが緩やかになる"
        
        # 最大高さ (任意: アンカー間距離の20%程度とする)
        max_h = dist * 0.2
        current_h = max_h * (1.0 - self.muscle.contraction_ratio)
        
        # 直線の場合
        if current_h < 0.1:
            for i in range(num_points):
                t = i / (num_points - 1)
                pt = p1.add(vec.multiply(t))
                points.append(pt)
            return points
            
        # 円弧の場合
        # 弦の中点
        mid = p1.add(p2).multiply(0.5)
        
        # アーチの方向 (上方向)
        # Z軸方向を優先、もしZ軸並行ならX軸
        direction = vec.normalize()
        if abs(direction.z) < 0.9:
            up = FreeCAD.Vector(0, 0, 1)
        else:
            up = FreeCAD.Vector(1, 0, 0)
            
        normal = direction.cross(up).normalize()
        arch_dir = normal.cross(direction).normalize()
        
        # 円弧の計算
        # 弦長 L = dist, 高さ h = current_h
        # R = ( (L/2)^2 + h^2 ) / (2h)
        L = dist
        h = current_h
        R = ((L/2)**2 + h**2) / (2*h)
        
        # 中心から弦までの距離 d = R - h
        d_center = R - h
        
        # 円の中心
        center = mid.sub(arch_dir.multiply(d_center))
        
        # 角度計算
        # 始点ベクトル (center -> p1)
        v_start = p1.sub(center)
        # 終点ベクトル (center -> p2)
        v_end = p2.sub(center)
        
        # 2ベクトル間の角度 (0 ~ pi)
        total_angle = v_start.getAngle(v_end)
        
        # 回転軸
        rot_axis = v_start.cross(v_end).normalize() # normalと同じはず
        
        for i in range(num_points):
            t = i / (num_points - 1)
            # 現在の角度
            angle = total_angle * t
            
            # v_start を angle だけ回転
            rot = FreeCAD.Rotation(rot_axis, math.degrees(angle))
            v_current = rot.multVec(v_start)
            
            pt = center.add(v_current)
            points.append(pt)
            
        return points

    def update_muscle(self):
        """
        筋肉の形状と色を更新
        """
        doc = self.doc
        if not doc:
            return

        p1, p2 = self._get_anchor_positions()
        if p1 is None:
            return

        # アンカー間の距離
        anchor_dist = p1.sub(p2).Length
        
        # 筋肉の太さ (体積一定)
        # 長さは円弧長になるが、簡易的にアンカー間距離ベースで計算
        # あるいは正確に円弧長を出すことも可能だが、見た目重視ならこれで十分
        # 収縮すると太くなる
        # current_len ~ anchor_dist (or arc length)
        # 半径 R_muscle(太さ) は収縮率で決める方が安定する
        # R_muscle = R0 * (1 + 0.3 * ratio) ?
        # 元の計算: V = pi * r^2 * L.
        # ここでは L を anchor_dist * (1 + something) とみなすか?
        # 簡易的に: 収縮率に応じて太くする
        base_radius = self.muscle.diameter / 2.0
        # 膨張率
        expansion = 1.0 + self.muscle.contraction_ratio * 0.5 # 最大1.5倍
        current_radius = base_radius * expansion
        
        ratio = self.muscle.contraction_ratio
        current_color = (0.5 + 0.5 * ratio, 0.1, 1.0 - ratio)

        # セグメントの配置計算
        # N個のセグメント -> N+1個の点が必要
        num_segments = self.muscle.segments
        points = self.get_arc_points(p1, p2, num_segments + 1)
        
        for i in range(num_segments):
            obj_name = f"{self.muscle.name}_Seg_{i}"
            cylinder = doc.getObject(obj_name)
            
            if cylinder:
                pt_start = points[i]
                pt_end = points[i+1]
                
                # ベクトル
                vec_seg = pt_end.sub(pt_start)
                length_seg = vec_seg.Length
                
                # 形状更新
                cylinder.Radius = current_radius
                cylinder.Height = length_seg
                
                # 回転と配置
                # Cylinderはデフォルトで(0,0,1)方向を向いている
                # これを vec_seg方向に回転させる
                rot = FreeCAD.Rotation(FreeCAD.Vector(0,0,1), vec_seg.normalize())
                
                # 位置は始点
                cylinder.Placement = FreeCAD.Placement(pt_start, rot)

                if hasattr(cylinder, "ViewObject"):
                    cylinder.ViewObject.ShapeColor = current_color
        
        doc.recompute()

    def remove(self):
        """
        人工筋肉を削除
        """
        for cylinder in self.cylinders:
            self.doc.removeObject(cylinder.Name)
        self.cylinders.clear()

    def rebuild(self):
        """
        再構築（アンカー変更時など）
        """
        self.remove()
        self.create_muscle()


class MuscleControlPanel(QtGui.QWidget):
    """
    人工筋肉制御パネル
    """
    def __init__(self, muscle_parts):
        super().__init__()
        self.muscle_parts = muscle_parts # List of MusclePart
        self.current_muscle_part = muscle_parts[0]
        self.animation_timer = None
        self.init_ui()
    
    def init_ui(self):
        """
        UIの初期化
        """
        self.setWindowTitle("人工筋肉マネージャー")
        self.setGeometry(100, 100, 450, 400)
        self.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint) # 常に最前面
        
        layout = QtGui.QVBoxLayout()
        
        # タイトル
        title = QtGui.QLabel("Multi-Fiber Muscle Sim")
        title.setStyleSheet("font-size: 14pt; font-weight: bold;")
        title.setAlignment(QtCore.Qt.AlignCenter)
        layout.addWidget(title)
        
        # 筋肉選択コンボボックス
        sel_layout = QtGui.QHBoxLayout()
        sel_layout.addWidget(QtGui.QLabel("操作対象:"))
        self.combo = QtGui.QComboBox()
        self.combo.addItem("All Muscles")
        for mp in self.muscle_parts:
            self.combo.addItem(mp.muscle.name)
        self.combo.currentIndexChanged.connect(self.on_muscle_select)
        sel_layout.addWidget(self.combo)
        layout.addLayout(sel_layout)

        # アンカー設定エリア
        anchor_group = QtGui.QGroupBox("アンカー設定 (選択対象のみ)")
        anchor_layout = QtGui.QVBoxLayout()
        
        h_layout = QtGui.QHBoxLayout()
        self.btn_set_start = QtGui.QPushButton("始点を変更")
        self.btn_set_start.clicked.connect(lambda: self.set_anchor('start'))
        h_layout.addWidget(self.btn_set_start)
        
        self.btn_set_end = QtGui.QPushButton("終点を変更")
        self.btn_set_end.clicked.connect(lambda: self.set_anchor('end'))
        h_layout.addWidget(self.btn_set_end)
        
        anchor_layout.addLayout(h_layout)
        anchor_layout.addWidget(QtGui.QLabel("※3Dビューでオブジェクトを1つ選択してからボタンを押してください"))
        anchor_group.setLayout(anchor_layout)
        layout.addWidget(anchor_group)

        # 収縮率スライダー
        self.slider_label = QtGui.QLabel("収縮率: 0%")
        layout.addWidget(self.slider_label)
        
        self.slider = QtGui.QSlider(QtCore.Qt.Horizontal)
        self.slider.setMinimum(0)
        self.slider.setMaximum(100)
        self.slider.setValue(0)
        self.slider.valueChanged.connect(self.on_slider_change)
        layout.addWidget(self.slider)
        
        # アニメーションボタン
        button_layout = QtGui.QHBoxLayout()
        animate_btn = QtGui.QPushButton("収縮・伸長アニメーション")
        animate_btn.clicked.connect(self.start_animation)
        button_layout.addWidget(animate_btn)
        
        stop_btn = QtGui.QPushButton("停止")
        stop_btn.clicked.connect(self.stop_animation)
        button_layout.addWidget(stop_btn)
        
        layout.addLayout(button_layout)
        
        # 閉じるボタン
        close_btn = QtGui.QPushButton("閉じる")
        close_btn.clicked.connect(self.close)
        layout.addWidget(close_btn)
        
        self.setLayout(layout)
        
        # 初期状態のUI更新
        self.on_muscle_select(0)

    def on_muscle_select(self, index):
        """
        コンボボックス変更時の処理
        """
        if index == 0:
            # All Muscles
            self.current_muscle_part = None
            self.btn_set_start.setEnabled(False)
            self.btn_set_end.setEnabled(False)
        else:
            self.current_muscle_part = self.muscle_parts[index - 1]
            self.btn_set_start.setEnabled(True)
            self.btn_set_end.setEnabled(True)
            
            # スライダーの値をその筋肉の状態に合わせる
            val = int(self.current_muscle_part.muscle.contraction_ratio * 100)
            self.slider.blockSignals(True)
            self.slider.setValue(val)
            self.slider.blockSignals(False)
            self.slider_label.setText(f"収縮率: {val}%")

    def set_anchor(self, target):
        """
        アンカーを現在の選択オブジェクトに変更
        """
        if not self.current_muscle_part:
            return

        sel = FreeCADGui.Selection.getSelection()
        if len(sel) != 1:
            QtGui.QMessageBox.warning(self, "エラー", "オブジェクトを1つ選択してください。")
            return
            
        obj_name = sel[0].Name
        
        if target == 'start':
            self.current_muscle_part.muscle.start_object_name = obj_name
        else:
            self.current_muscle_part.muscle.end_object_name = obj_name
            
        # 再構築（位置が変わるため）
        self.current_muscle_part.rebuild()
        print(f"Updated {self.current_muscle_part.muscle.name} {target} anchor to {obj_name}")

    def on_slider_change(self, value):
        ratio = value / 100.0
        self.slider_label.setText(f"収縮率: {value}%")
        
        targets = []
        if self.current_muscle_part:
            targets = [self.current_muscle_part]
        else:
            targets = self.muscle_parts
            
        for mp in targets:
            mp.muscle.set_contraction(ratio)
            mp.update_muscle()
            
        # FreeCADGui.updateGui()

    def start_animation(self):
        if self.animation_timer is not None:
            self.animation_timer.stop()
        
        self.animation_direction = 1
        self.animation_timer = QtCore.QTimer(self)
        self.animation_timer.timeout.connect(self.animate_step)
        self.animation_timer.start(50)
    
    def animate_step(self):
        current_value = self.slider.value()
        new_value = current_value + self.animation_direction * 2
        
        if new_value >= 100:
            new_value = 100
            self.animation_direction = -1
        elif new_value <= 0:
            new_value = 0
            self.animation_direction = 1
        
        self.slider.setValue(new_value)
    
    def stop_animation(self):
        if self.animation_timer is not None:
            self.animation_timer.stop()
            self.animation_timer = None


def setup_scene():
    """
    10個の球体を生成し、5ペアのリストを返す
    """
    doc = FreeCAD.activeDocument()
    
    # 既存オブジェクトのクリーンアップ（テスト用）
    for obj in doc.Objects:
        if obj.Name.startswith("AnchorSphere_") or obj.Name.startswith("Muscle_"):
             doc.removeObject(obj.Name)

    anchors = []
    # 5ペア = 10個
    for i in range(5):
        # Start Sphere
        s1 = doc.addObject("Part::Sphere", f"AnchorSphere_Start_{i+1}")
        s1.Radius = 5
        # 配置: Y軸方向に並べる, X=0
        s1.Placement.Base = FreeCAD.Vector(0, i * 30, 0)
        
        # End Sphere
        s2 = doc.addObject("Part::Sphere", f"AnchorSphere_End_{i+1}")
        s2.Radius = 5
        # 配置: Y軸方向に並べる, X=100 (筋肉の長さ100mm)
        s2.Placement.Base = FreeCAD.Vector(100, i * 30, 0)
        
        anchors.append((s1.Name, s2.Name))
        
    doc.recompute()
    return anchors

def main():
    print("=" * 50)
    print("FreeCAD マルチ人工筋肉シミュレーター")
    print("=" * 50)
    
    doc = FreeCAD.activeDocument()
    if doc is None:
        doc = FreeCAD.newDocument("ArtificialMuscle")
    elif doc.Name != "ArtificialMuscle":
        pass
    
    if FreeCAD.ActiveDocument:
        FreeCADGui.setActiveDocument(FreeCAD.ActiveDocument)
    
    # シーンセットアップ
    print("シーンを構築中...")
    anchor_pairs = setup_scene()

    # 筋肉生成
    print("人工筋肉を生成中...")
    muscle_parts = []
    for i, (start_name, end_name) in enumerate(anchor_pairs):
        # 距離計算
        p1 = doc.getObject(start_name).Shape.CenterOfMass
        p2 = doc.getObject(end_name).Shape.CenterOfMass
        dist = p1.sub(p2).Length
        
        muscle = ArtificialMuscle(
            name=f"Muscle_{i+1}",
            length=dist,
            diameter=5,
            segments=5, # デフォルト5セグメント
            start_obj_name=start_name,
            end_obj_name=end_name
        )
        mp = MusclePart(doc, muscle)
        muscle_parts.append(mp)
    
    # ビュー調整
    if FreeCADGui.activeDocument() is not None:
        view = FreeCADGui.activeDocument().activeView()
        if view is not None:
            view.viewAxonometric()
            view.fitAll()

    # コントロールパネル
    panel = MuscleControlPanel(muscle_parts)
    panel.show()
    
    # FreeCADGuiのイベントループに任せるため、ここでは保持するだけ
    # 必要ならグローバル変数に退避
    global _muscle_panel
    _muscle_panel = panel

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\nエラーが発生しました: {e}")
        import traceback
        traceback.print_exc()

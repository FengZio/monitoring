import React from "react";
import { Modal, Radio, Space, Typography } from "antd";

interface FenceModeDialogProps {
  open: boolean;
  onOk: (mode: string) => void;
  onCancel: () => void;
}

const FenceModeDialog: React.FC<FenceModeDialogProps> = ({ open, onOk, onCancel }) => {
  const [mode, setMode] = React.useState("restricted");

  return (
    <Modal
      title="围栏模式"
      open={open}
      onOk={() => onOk(mode)}
      onCancel={onCancel}
      okText="保存"
      cancelText="取消"
      width={420}
    >
      <Radio.Group value={mode} onChange={(e) => setMode(e.target.value)}>
        <Space direction="vertical" size={12} style={{ width: "100%" }}>
          <Radio value="restricted">
            <div>
              <Typography.Text strong>禁入模式 (restricted)</Typography.Text>
              <br />
              <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                目标从外部进入围栏区域时触发告警。已在区域内的目标不会重复告警。
              </Typography.Text>
            </div>
          </Radio>
          <Radio value="enclosure">
            <div>
              <Typography.Text strong>禁出模式 (enclosure)</Typography.Text>
              <br />
              <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                目标从围栏区域内离开时触发告警。外部进入的目标不会触发告警。
              </Typography.Text>
            </div>
          </Radio>
        </Space>
      </Radio.Group>
    </Modal>
  );
};

export default FenceModeDialog;
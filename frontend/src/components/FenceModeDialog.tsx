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
      title="fence mode"
      open={open}
      onOk={() => onOk(mode)}
      onCancel={onCancel}
      okText="save"
      width={420}
    >
      <Radio.Group value={mode} onChange={(e) => setMode(e.target.value)}>
        <Space direction="vertical" size={12} style={{ width: "100%" }}>
          <Radio value="restricted">
            <div>
              <Typography.Text strong>restricted zone</Typography.Text>
              <br />
              <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                alert when someone enters the fence from outside.
                people already inside won't trigger alerts.
              </Typography.Text>
            </div>
          </Radio>
          <Radio value="enclosure">
            <div>
              <Typography.Text strong>enclosure</Typography.Text>
              <br />
              <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                alert when someone leaves the fenced area.
                people outside entering won't trigger alerts.
              </Typography.Text>
            </div>
          </Radio>
        </Space>
      </Radio.Group>
    </Modal>
  );
};

export default FenceModeDialog;

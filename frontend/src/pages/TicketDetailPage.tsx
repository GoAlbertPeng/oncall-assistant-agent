import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Card,
  Descriptions,
  Button,
  Space,
  Tag,
  Typography,
  message,
  Spin,
  Divider,
  Select,
  Modal,
} from 'antd';
import {
  ArrowLeftOutlined,
  EditOutlined,
  CheckCircleOutlined,
} from '@ant-design/icons';
import { ticketApi, Ticket } from '../services/api';

const { Title, Paragraph } = Typography;

const statusColors: Record<string, string> = {
  new: 'blue',
  processing: 'orange',
  closed: 'green',
};

const statusLabels: Record<string, string> = {
  new: '新建',
  processing: '处理中',
  closed: '已完结',
};

const levelColors: Record<string, string> = {
  P1: 'red',
  P2: 'orange',
  P3: 'default',
};

export default function TicketDetailPage() {
  const { ticketNo } = useParams<{ ticketNo: string }>();
  const navigate = useNavigate();
  const [ticket, setTicket] = useState<Ticket | null>(null);
  const [loading, setLoading] = useState(true);
  const [updating, setUpdating] = useState(false);

  useEffect(() => {
    if (ticketNo) {
      loadTicket();
    }
  }, [ticketNo]);

  const loadTicket = async () => {
    if (!ticketNo) return;
    setLoading(true);
    try {
      const response = await ticketApi.get(ticketNo);
      setTicket(response.data);
    } catch {
      message.error('加载工单详情失败');
    } finally {
      setLoading(false);
    }
  };

  const handleStatusChange = async (newStatus: 'new' | 'processing' | 'closed') => {
    if (!ticketNo || !ticket) return;

    // Confirm for closing
    if (newStatus === 'closed') {
      Modal.confirm({
        title: '确认完结工单？',
        content: '工单完结后状态将无法更改',
        onOk: async () => {
          await updateStatus(newStatus);
        },
      });
    } else {
      await updateStatus(newStatus);
    }
  };

  const updateStatus = async (newStatus: 'new' | 'processing' | 'closed') => {
    if (!ticketNo) return;
    setUpdating(true);
    try {
      const response = await ticketApi.update(ticketNo, { status: newStatus });
      setTicket(response.data);
      message.success('状态更新成功');
    } catch {
      message.error('状态更新失败');
    } finally {
      setUpdating(false);
    }
  };

  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: 50 }}>
        <Spin size="large" />
      </div>
    );
  }

  if (!ticket) {
    return (
      <div style={{ textAlign: 'center', padding: 50 }}>
        <Title level={4}>工单不存在</Title>
        <Button onClick={() => navigate('/tickets')}>返回列表</Button>
      </div>
    );
  }

  return (
    <div>
      <div style={{ marginBottom: 16 }}>
        <Button
          icon={<ArrowLeftOutlined />}
          onClick={() => navigate('/tickets')}
        >
          返回列表
        </Button>
      </div>

      <Card>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Title level={4} style={{ margin: 0 }}>
            工单详情 - {ticket.ticket_no}
          </Title>
          <Space>
            {ticket.status !== 'closed' && (
              <Select
                value={ticket.status}
                onChange={handleStatusChange}
                loading={updating}
                style={{ width: 120 }}
                options={[
                  { value: 'new', label: '新建' },
                  { value: 'processing', label: '处理中' },
                  { value: 'closed', label: '已完结' },
                ]}
              />
            )}
          </Space>
        </div>

        <Divider />

        <Descriptions column={2} bordered>
          <Descriptions.Item label="工单号">{ticket.ticket_no}</Descriptions.Item>
          <Descriptions.Item label="状态">
            <Tag color={statusColors[ticket.status]}>
              {ticket.status === 'closed' && <CheckCircleOutlined style={{ marginRight: 4 }} />}
              {statusLabels[ticket.status]}
            </Tag>
          </Descriptions.Item>
          <Descriptions.Item label="故障等级">
            <Tag color={levelColors[ticket.level]}>{ticket.level}</Tag>
          </Descriptions.Item>
          <Descriptions.Item label="关联分析">
            {ticket.session_id ? (
              <Button type="link" size="small" onClick={() => navigate('/analysis')}>
                查看分析 #{ticket.session_id}
              </Button>
            ) : (
              '-'
            )}
          </Descriptions.Item>
          <Descriptions.Item label="创建时间">
            {new Date(ticket.created_at).toLocaleString()}
          </Descriptions.Item>
          <Descriptions.Item label="完结时间">
            {ticket.closed_at ? new Date(ticket.closed_at).toLocaleString() : '-'}
          </Descriptions.Item>
          <Descriptions.Item label="标题" span={2}>
            {ticket.title}
          </Descriptions.Item>
          <Descriptions.Item label="根因结论" span={2}>
            <Paragraph style={{ margin: 0, whiteSpace: 'pre-wrap' }}>
              {ticket.root_cause || '暂无'}
            </Paragraph>
          </Descriptions.Item>
        </Descriptions>

        {ticket.status !== 'closed' && (
          <>
            <Divider />
            <div style={{ textAlign: 'center' }}>
              <Space>
                {ticket.status === 'new' && (
                  <Button
                    type="primary"
                    icon={<EditOutlined />}
                    onClick={() => handleStatusChange('processing')}
                    loading={updating}
                  >
                    开始处理
                  </Button>
                )}
                {ticket.status === 'processing' && (
                  <Button
                    type="primary"
                    icon={<CheckCircleOutlined />}
                    onClick={() => handleStatusChange('closed')}
                    loading={updating}
                  >
                    完结工单
                  </Button>
                )}
              </Space>
            </div>
          </>
        )}
      </Card>
    </div>
  );
}

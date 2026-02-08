import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Card,
  Table,
  Button,
  Space,
  Tag,
  Select,
  DatePicker,
  Typography,
  message,
} from 'antd';
import { EyeOutlined, ReloadOutlined } from '@ant-design/icons';
import { ticketApi, Ticket, TicketListResponse } from '../services/api';
import dayjs from 'dayjs';

const { Title, Text } = Typography;
const { RangePicker } = DatePicker;

const statusOptions = [
  { value: '', label: '全部状态' },
  { value: 'new', label: '新建' },
  { value: 'processing', label: '处理中' },
  { value: 'closed', label: '已完结' },
];

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

export default function TicketsPage() {
  const navigate = useNavigate();
  const [data, setData] = useState<TicketListResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [filters, setFilters] = useState<{
    status?: string;
    dateRange?: [dayjs.Dayjs, dayjs.Dayjs];
    page: number;
    pageSize: number;
  }>({
    page: 1,
    pageSize: 20,
  });

  useEffect(() => {
    loadTickets();
  }, [filters]);

  const loadTickets = async () => {
    setLoading(true);
    try {
      const params: Record<string, unknown> = {
        page: filters.page,
        page_size: filters.pageSize,
      };
      if (filters.status) {
        params.status = filters.status;
      }
      if (filters.dateRange) {
        params.start_date = filters.dateRange[0].toISOString();
        params.end_date = filters.dateRange[1].toISOString();
      }

      const response = await ticketApi.list(params as Parameters<typeof ticketApi.list>[0]);
      setData(response.data);
    } catch {
      message.error('加载工单列表失败');
    } finally {
      setLoading(false);
    }
  };

  const columns = [
    {
      title: '工单号',
      dataIndex: 'ticket_no',
      key: 'ticket_no',
      render: (no: string) => <Text copyable>{no}</Text>,
    },
    {
      title: '标题',
      dataIndex: 'title',
      key: 'title',
      ellipsis: true,
    },
    {
      title: '等级',
      dataIndex: 'level',
      key: 'level',
      render: (level: string) => <Tag color={levelColors[level]}>{level}</Tag>,
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      render: (status: string) => (
        <Tag color={statusColors[status]}>{statusLabels[status]}</Tag>
      ),
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      render: (time: string) => new Date(time).toLocaleString(),
    },
    {
      title: '完结时间',
      dataIndex: 'closed_at',
      key: 'closed_at',
      render: (time: string | null) =>
        time ? new Date(time).toLocaleString() : '-',
    },
    {
      title: '操作',
      key: 'actions',
      render: (_: unknown, record: Ticket) => (
        <Button
          type="link"
          icon={<EyeOutlined />}
          onClick={() => navigate(`/tickets/${record.ticket_no}`)}
        >
          查看
        </Button>
      ),
    },
  ];

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
        <div>
          <Title level={4}>工单管理</Title>
          <Text type="secondary">查看和管理告警相关的工单</Text>
        </div>
        <Button icon={<ReloadOutlined />} onClick={loadTickets}>
          刷新
        </Button>
      </div>

      <Card>
        <Space style={{ marginBottom: 16 }}>
          <Select
            style={{ width: 150 }}
            placeholder="状态筛选"
            options={statusOptions}
            value={filters.status || ''}
            onChange={(value) => setFilters({ ...filters, status: value, page: 1 })}
          />
          <RangePicker
            value={filters.dateRange}
            onChange={(dates) =>
              setFilters({
                ...filters,
                dateRange: dates as [dayjs.Dayjs, dayjs.Dayjs] | undefined,
                page: 1,
              })
            }
          />
        </Space>

        <Table
          columns={columns}
          dataSource={data?.items || []}
          rowKey="ticket_no"
          loading={loading}
          pagination={{
            current: filters.page,
            pageSize: filters.pageSize,
            total: data?.total || 0,
            showSizeChanger: true,
            showQuickJumper: true,
            showTotal: (total) => `共 ${total} 条`,
            onChange: (page, pageSize) =>
              setFilters({ ...filters, page, pageSize }),
          }}
        />
      </Card>
    </div>
  );
}

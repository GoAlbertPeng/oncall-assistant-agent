import { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Card,
  Input,
  Button,
  Space,
  Typography,
  Divider,
  Tag,
  List,
  message,
  Progress,
  Collapse,
  Modal,
  Form,
  Select,
  Steps,
} from 'antd';
import {
  SendOutlined,
  FileAddOutlined,
  HistoryOutlined,
  CheckCircleOutlined,
  ExclamationCircleOutlined,
  BulbOutlined,
  ToolOutlined,
  LoadingOutlined,
  StopOutlined,
  ReloadOutlined,
  SearchOutlined,
  DatabaseOutlined,
  RobotOutlined,
  DeleteOutlined,
} from '@ant-design/icons';
import {
  analysisApi,
  ticketApi,
  AnalysisResponse,
  AnalysisListItem,
  StreamEvent,
} from '../services/api';

const { TextArea } = Input;
const { Title, Text, Paragraph } = Typography;

const categoryMap: Record<string, { label: string; color: string }> = {
  code_issue: { label: '代码问题', color: 'red' },
  config_issue: { label: '配置问题', color: 'orange' },
  resource_bottleneck: { label: '资源瓶颈', color: 'blue' },
  dependency_failure: { label: '依赖故障', color: 'purple' },
};

const stageInfo: Record<string, { title: string; icon: React.ReactNode }> = {
  intent_understanding: { title: '意图理解', icon: <SearchOutlined /> },
  data_collection: { title: '数据收集', icon: <DatabaseOutlined /> },
  llm_analysis: { title: 'AI分析', icon: <RobotOutlined /> },
};

interface ChatMessage {
  role: 'user' | 'assistant' | 'system';
  content: string;
  stage?: string;
  timestamp: string;
}

export default function AnalysisPage() {
  const navigate = useNavigate();
  const [alertContent, setAlertContent] = useState('');
  const [analyzing, setAnalyzing] = useState(false);
  const [currentStage, setCurrentStage] = useState<string | null>(null);
  const [stageProgress, setStageProgress] = useState(0);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [sessionId, setSessionId] = useState<number | null>(null);
  const [result, setResult] = useState<AnalysisResponse | null>(null);
  const [history, setHistory] = useState<AnalysisListItem[]>([]);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [ticketModalOpen, setTicketModalOpen] = useState(false);
  const [followUpInput, setFollowUpInput] = useState('');
  const [ticketForm] = Form.useForm();
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const abortControllerRef = useRef<AbortController | null>(null);
  const sessionIdRef = useRef<number | null>(null);

  useEffect(() => {
    loadHistory();
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const loadHistory = async () => {
    setLoadingHistory(true);
    try {
      const response = await analysisApi.list(1, 10);
      setHistory(response.data);
    } catch {
      // Ignore error
    } finally {
      setLoadingHistory(false);
    }
  };

  const handleDeleteHistory = async (id: number, e: React.MouseEvent) => {
    e.stopPropagation(); // Prevent triggering the list item click
    try {
      await analysisApi.delete(id);
      message.success('删除成功');
      // Remove from local state
      setHistory(prev => prev.filter(item => item.id !== id));
      // Clear result if deleted session was being viewed
      if (sessionId === id) {
        setSessionId(null);
        setResult(null);
        setMessages([]);
      }
    } catch {
      message.error('删除失败');
    }
  };

  const addMessage = (msg: ChatMessage) => {
    setMessages(prev => [...prev, msg]);
  };

  const handleStreamAnalysis = async () => {
    if (!alertContent.trim()) {
      message.warning('请输入告警信息');
      return;
    }

    setAnalyzing(true);
    setResult(null);
    setSessionId(null);
    sessionIdRef.current = null;
    setMessages([{ 
      role: 'user', 
      content: alertContent, 
      timestamp: new Date().toISOString() 
    }]);
    setCurrentStage(null);
    setStageProgress(0);

    const token = localStorage.getItem('token');
    if (!token) {
      message.error('请先登录');
      setAnalyzing(false);
      return;
    }

    abortControllerRef.current = new AbortController();

    try {
      const response = await fetch('/api/analysis/stream', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify({
          alert_content: alertContent,
          time_range_minutes: 30,
        }),
        signal: abortControllerRef.current.signal,
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      // Get session ID from header
      const sid = response.headers.get('X-Session-Id');
      if (sid) {
        const sidNum = parseInt(sid);
        sessionIdRef.current = sidNum;
        setSessionId(sidNum);
      }

      const reader = response.body?.getReader();
      const decoder = new TextDecoder();

      if (!reader) {
        throw new Error('No reader available');
      }

      let buffer = '';
      
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const event: StreamEvent = JSON.parse(line.slice(6));
              handleStreamEvent(event);
            } catch (e) {
              console.error('Failed to parse SSE event:', e);
            }
          }
        }
      }

      loadHistory();
    } catch (error: unknown) {
      if ((error as Error).name === 'AbortError') {
        addMessage({
          role: 'system',
          content: '⚠️ 分析已取消',
          timestamp: new Date().toISOString(),
        });
      } else {
        const err = error as { message?: string };
        message.error(err.message || '分析失败');
        addMessage({
          role: 'system',
          content: `❌ 分析失败: ${err.message || '未知错误'}`,
          timestamp: new Date().toISOString(),
        });
      }
    } finally {
      setAnalyzing(false);
      setCurrentStage(null);
      abortControllerRef.current = null;
    }
  };

  const handleStreamEvent = (event: StreamEvent) => {
    switch (event.event) {
      case 'stage_start':
        setCurrentStage(event.stage || null);
        setStageProgress(0);
        if (event.content) {
          addMessage({
            role: 'assistant',
            content: event.content,
            stage: event.stage,
            timestamp: new Date().toISOString(),
          });
        }
        break;

      case 'stage_progress':
        setStageProgress(event.progress || 0);
        if (event.content) {
          addMessage({
            role: 'assistant',
            content: event.content,
            stage: event.stage,
            timestamp: new Date().toISOString(),
          });
        }
        break;

      case 'stage_complete':
        setStageProgress(100);
        if (event.content) {
          addMessage({
            role: 'assistant',
            content: event.content,
            stage: event.stage,
            timestamp: new Date().toISOString(),
          });
        }
        break;

      case 'message':
        if (event.content) {
          addMessage({
            role: 'assistant',
            content: event.content,
            stage: event.stage,
            timestamp: new Date().toISOString(),
          });
        }
        break;

      case 'error':
        addMessage({
          role: 'system',
          content: `❌ ${event.content || '发生错误'}`,
          timestamp: new Date().toISOString(),
        });
        break;

      case 'cancelled':
        addMessage({
          role: 'system',
          content: '⚠️ 分析已取消',
          timestamp: new Date().toISOString(),
        });
        break;

      case 'done':
        // Load the full result using ref (state might not be updated yet)
        const sid = sessionIdRef.current || (event.data?.session_id as number);
        if (sid) {
          analysisApi.get(sid).then(res => {
            setResult(res.data);
          }).catch(err => {
            console.error('Failed to load result:', err);
          });
        }
        break;
    }
  };

  const handleCancel = async () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    if (sessionId) {
      try {
        await analysisApi.cancel(sessionId);
      } catch {
        // Ignore
      }
    }
  };

  const handleReanalyze = async () => {
    if (!sessionId) return;
    
    setAnalyzing(true);
    setMessages(prev => [...prev, {
      role: 'user',
      content: '[重新分析]',
      timestamp: new Date().toISOString(),
    }]);

    const token = localStorage.getItem('token');
    if (!token) return;

    try {
      const response = await fetch(`/api/analysis/${sessionId}/reanalyze`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      });

      const reader = response.body?.getReader();
      const decoder = new TextDecoder();

      if (!reader) return;

      let buffer = '';
      
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const event: StreamEvent = JSON.parse(line.slice(6));
              handleStreamEvent(event);
            } catch (e) {
              console.error('Failed to parse SSE event:', e);
            }
          }
        }
      }
    } catch (error) {
      message.error('重新分析失败');
    } finally {
      setAnalyzing(false);
    }
  };

  const handleContinue = async () => {
    if (!sessionId || !followUpInput.trim()) return;

    const userMessage = followUpInput;
    setFollowUpInput('');
    
    addMessage({
      role: 'user',
      content: userMessage,
      timestamp: new Date().toISOString(),
    });

    setAnalyzing(true);

    const token = localStorage.getItem('token');
    if (!token) return;

    try {
      const response = await fetch(`/api/analysis/${sessionId}/continue`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify({ message: userMessage }),
      });

      const reader = response.body?.getReader();
      const decoder = new TextDecoder();

      if (!reader) return;

      let buffer = '';
      
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const event: StreamEvent = JSON.parse(line.slice(6));
              handleStreamEvent(event);
            } catch (e) {
              console.error('Failed to parse SSE event:', e);
            }
          }
        }
      }
    } catch (error) {
      message.error('处理失败');
    } finally {
      setAnalyzing(false);
    }
  };

  const handleViewHistory = async (item: AnalysisListItem) => {
    try {
      const response = await analysisApi.get(item.id);
      setResult(response.data);
      setAlertContent(response.data.alert_content);
      setSessionId(response.data.id);
      
      // Convert messages from API response
      setMessages(response.data.messages.map(msg => ({
        role: msg.role as 'user' | 'assistant' | 'system',
        content: msg.content,
        stage: msg.stage,
        timestamp: msg.timestamp,
      })));
    } catch {
      message.error('加载失败');
    }
  };

  const handleCreateTicket = () => {
    if (!result?.analysis_result) {
      message.warning('请先进行告警分析');
      return;
    }
    
    // 根据问题类型自动推荐等级
    const categoryToLevel: Record<string, 'P1' | 'P2' | 'P3'> = {
      'resource_bottleneck': 'P1',
      'dependency_failure': 'P1',
      'code_issue': 'P2',
      'config_issue': 'P2',
    };
    const recommendedLevel = categoryToLevel[result.analysis_result.category] || 'P3';
    
    // 生成AI分析摘要
    const aiAnalysisSummary = `【AI分析报告】
告警内容: ${alertContent}

🎯 根因分析: 
${result.analysis_result.root_cause}

📋 分析依据: 
${result.analysis_result.evidence}

🏷️ 问题分类: ${categoryMap[result.analysis_result.category]?.label || result.analysis_result.category}

🚑 临时解决方案: 
${result.analysis_result.temporary_solution}

🔧 根本解决方案: 
${result.analysis_result.permanent_solution}

📊 置信度: ${((result.analysis_result.confidence || 0) * 100).toFixed(0)}%`;

    ticketForm.setFieldsValue({
      title: `[${categoryMap[result.analysis_result.category]?.label || '告警'}] ${alertContent.slice(0, 40)}`,
      root_cause: result.analysis_result.root_cause,
      ai_analysis: aiAnalysisSummary,
      level: recommendedLevel,
    });
    setTicketModalOpen(true);
  };

  const submitTicket = async (values: { title: string; root_cause: string; ai_analysis: string; level: 'P1' | 'P2' | 'P3' }) => {
    try {
      const response = await ticketApi.create({
        session_id: result?.id,
        title: values.title,
        root_cause: values.root_cause,
        ai_analysis: values.ai_analysis,
        level: values.level,
      });
      message.success(`工单创建成功: ${response.data.ticket_no}`);
      setTicketModalOpen(false);
      navigate(`/tickets/${response.data.ticket_no}`);
    } catch {
      message.error('创建工单失败');
    }
  };

  const getCurrentStep = () => {
    if (!currentStage) return -1;
    const stages = ['intent_understanding', 'data_collection', 'llm_analysis'];
    return stages.indexOf(currentStage);
  };

  return (
    <div>
      <Title level={4}>智能告警分析</Title>
      <Text type="secondary">输入告警信息，系统将分阶段进行智能分析</Text>

      <div style={{ display: 'flex', gap: 24, marginTop: 24 }}>
        {/* 左侧：对话界面 */}
        <div style={{ flex: 1 }}>
          {/* 输入区域 */}
          <Card title="告警信息" size="small">
            <TextArea
              rows={3}
              placeholder="请输入告警信息，例如：支付服务 CPU 使用率 99%，持续 5 分钟"
              value={alertContent}
              onChange={(e) => setAlertContent(e.target.value)}
              disabled={analyzing}
            />
            <div style={{ marginTop: 12, textAlign: 'right' }}>
              <Space>
                {analyzing ? (
                  <Button
                    danger
                    icon={<StopOutlined />}
                    onClick={handleCancel}
                  >
                    取消分析
                  </Button>
                ) : (
                  <Button
                    type="primary"
                    icon={<SendOutlined />}
                    onClick={handleStreamAnalysis}
                  >
                    开始分析
                  </Button>
                )}
                <Button
                  icon={<FileAddOutlined />}
                  onClick={handleCreateTicket}
                  disabled={!result?.analysis_result}
                >
                  生成工单
                </Button>
              </Space>
            </div>
          </Card>

          {/* 分析进度 */}
          {analyzing && currentStage && (
            <Card size="small" style={{ marginTop: 16 }}>
              <Steps
                current={getCurrentStep()}
                size="small"
                items={[
                  {
                    title: '意图理解',
                    icon: currentStage === 'intent_understanding' ? <LoadingOutlined /> : <SearchOutlined />,
                  },
                  {
                    title: '数据收集',
                    icon: currentStage === 'data_collection' ? <LoadingOutlined /> : <DatabaseOutlined />,
                  },
                  {
                    title: 'AI分析',
                    icon: currentStage === 'llm_analysis' ? <LoadingOutlined /> : <RobotOutlined />,
                  },
                ]}
              />
              {stageProgress > 0 && stageProgress < 100 && (
                <Progress percent={stageProgress} size="small" style={{ marginTop: 12 }} />
              )}
            </Card>
          )}

          {/* 分析过程 - 仅在分析中显示 */}
          {analyzing && messages.length > 0 && (
            <Card 
              title="分析进行中..." 
              size="small" 
              style={{ marginTop: 16 }}
              styles={{ body: { maxHeight: 400, overflowY: 'auto', padding: '12px 16px' } }}
            >
              <div>
                {messages.map((msg, index) => (
                  <div
                    key={index}
                    style={{
                      marginBottom: 8,
                      padding: '6px 10px',
                      borderRadius: 6,
                      backgroundColor: msg.role === 'user' 
                        ? '#e6f7ff' 
                        : msg.role === 'system' 
                          ? '#fff7e6' 
                          : '#f6ffed',
                      fontSize: 13,
                    }}
                  >
                    {msg.stage && (
                      <Tag style={{ marginRight: 8, fontSize: 11 }}>
                        {stageInfo[msg.stage]?.title || msg.stage}
                      </Tag>
                    )}
                    <span>{msg.content.replace(/[#*]/g, '').substring(0, 100)}</span>
                  </div>
                ))}
                <div ref={messagesEndRef} />
              </div>
            </Card>
          )}

          {/* 追问输入 */}
          {sessionId && !analyzing && result?.status === 'completed' && (
            <Card size="small" style={{ marginTop: 16 }}>
              <Space.Compact style={{ width: '100%' }}>
                <Input
                  placeholder="继续提问或请求进一步分析..."
                  value={followUpInput}
                  onChange={(e) => setFollowUpInput(e.target.value)}
                  onPressEnter={handleContinue}
                />
                <Button type="primary" onClick={handleContinue}>
                  发送
                </Button>
                <Button icon={<ReloadOutlined />} onClick={handleReanalyze}>
                  重新分析
                </Button>
              </Space.Compact>
            </Card>
          )}

          {/* 分析结果 - 分析完成后直接展示 */}
          {result && result.analysis_result && !analyzing && (
            <Card 
              title={
                <Space>
                  <CheckCircleOutlined style={{ color: '#52c41a' }} />
                  <span>分析结果</span>
                  <Tag color={categoryMap[result.analysis_result.category]?.color || 'default'}>
                    {categoryMap[result.analysis_result.category]?.label || result.analysis_result.category}
                  </Tag>
                  {result.analysis_result.confidence && (
                    <Text type="secondary" style={{ fontSize: 13 }}>
                      置信度: {(result.analysis_result.confidence * 100).toFixed(0)}%
                    </Text>
                  )}
                </Space>
              }
              size="small" 
              style={{ marginTop: 16 }}
            >
              <Divider orientation="left" style={{ margin: '8px 0' }}>
                <ExclamationCircleOutlined /> 根因结论
              </Divider>
              <Paragraph style={{ marginLeft: 16, fontSize: 14 }}>{result.analysis_result.root_cause}</Paragraph>

              <Divider orientation="left" style={{ margin: '12px 0 8px' }}>
                <CheckCircleOutlined /> 证据说明
              </Divider>
              <Paragraph style={{ marginLeft: 16, fontSize: 14 }}>{result.analysis_result.evidence}</Paragraph>

              <Divider orientation="left" style={{ margin: '12px 0 8px' }}>
                <BulbOutlined /> 临时缓解方案
              </Divider>
              <Paragraph style={{ marginLeft: 16, fontSize: 14 }}>{result.analysis_result.temporary_solution}</Paragraph>

              <Divider orientation="left" style={{ margin: '12px 0 8px' }}>
                <ToolOutlined /> 根本解决方案
              </Divider>
              <Paragraph style={{ marginLeft: 16, fontSize: 14 }}>{result.analysis_result.permanent_solution}</Paragraph>

              <Collapse
                style={{ marginTop: 16 }}
                items={[
                  {
                    key: 'details',
                    label: '查看详细上下文信息',
                    children: (
                      <>
                        {result.context_data && (
                          <>
                            {result.context_data.logs && result.context_data.logs.length > 0 && (
                              <>
                                <Text strong>相关日志 ({result.context_data.logs.length}条):</Text>
                                <pre style={{ 
                                  fontSize: 12, 
                                  maxHeight: 150, 
                                  overflow: 'auto', 
                                  backgroundColor: '#f5f5f5',
                                  padding: 8,
                                  borderRadius: 4,
                                  marginTop: 8
                                }}>
                                  {result.context_data.logs.slice(0, 10).map((log) => 
                                    `[${log.timestamp}] ${log.level}: ${log.message}\n`
                                  ).join('')}
                                  {result.context_data.logs.length > 10 && `... 还有 ${result.context_data.logs.length - 10} 条日志`}
                                </pre>
                              </>
                            )}
                            {result.context_data.metrics && result.context_data.metrics.length > 0 && (
                              <>
                                <Text strong style={{ display: 'block', marginTop: 12 }}>
                                  相关指标 ({result.context_data.metrics.length}条):
                                </Text>
                                <pre style={{ 
                                  fontSize: 12, 
                                  maxHeight: 150, 
                                  overflow: 'auto', 
                                  backgroundColor: '#f5f5f5',
                                  padding: 8,
                                  borderRadius: 4,
                                  marginTop: 8
                                }}>
                                  {result.context_data.metrics.slice(0, 10).map((m) => 
                                    `${m.name}: ${m.value} @ ${m.timestamp}\n`
                                  ).join('')}
                                  {result.context_data.metrics.length > 10 && `... 还有 ${result.context_data.metrics.length - 10} 条指标`}
                                </pre>
                              </>
                            )}
                          </>
                        )}
                      </>
                    ),
                  },
                ]}
              />
            </Card>
          )}
        </div>

        {/* 右侧：历史记录 */}
        <div style={{ width: 280 }}>
          <Card
            title={
              <Space>
                <HistoryOutlined />
                <span>历史记录</span>
              </Space>
            }
            size="small"
            loading={loadingHistory}
          >
            <List
              size="small"
              dataSource={history}
              locale={{ emptyText: '暂无历史记录' }}
              renderItem={(item) => (
                <List.Item
                  style={{ cursor: 'pointer', padding: '8px 0' }}
                  onClick={() => handleViewHistory(item)}
                  actions={[
                    <Button
                      key="delete"
                      type="text"
                      size="small"
                      danger
                      icon={<DeleteOutlined />}
                      onClick={(e) => handleDeleteHistory(item.id, e)}
                    />
                  ]}
                >
                  <List.Item.Meta
                    title={
                      <Space size={4}>
                        <Text ellipsis style={{ maxWidth: 140, fontSize: 13 }}>
                          {item.alert_content}
                        </Text>
                        {item.has_result && <CheckCircleOutlined style={{ color: '#52c41a', fontSize: 12 }} />}
                      </Space>
                    }
                    description={
                      <Space size={4}>
                        <Tag color={item.status === 'completed' ? 'green' : item.status === 'error' ? 'red' : 'blue'} style={{ fontSize: 11 }}>
                          {item.status}
                        </Tag>
                        <Text type="secondary" style={{ fontSize: 11 }}>
                          {new Date(item.created_at).toLocaleString()}
                        </Text>
                      </Space>
                    }
                  />
                </List.Item>
              )}
            />
          </Card>
        </div>
      </div>

      {/* 创建工单弹窗 */}
      <Modal
        title="创建工单"
        open={ticketModalOpen}
        onCancel={() => setTicketModalOpen(false)}
        onOk={() => ticketForm.submit()}
        width={700}
      >
        <Form form={ticketForm} layout="vertical" onFinish={submitTicket}>
          <Form.Item
            name="title"
            label="工单标题"
            rules={[{ required: true, message: '请输入工单标题' }]}
          >
            <Input />
          </Form.Item>
          <Form.Item
            name="level"
            label="故障等级（AI推荐）"
            rules={[{ required: true }]}
          >
            <Select>
              <Select.Option value="P1">P1 - 紧急（资源瓶颈/依赖故障）</Select.Option>
              <Select.Option value="P2">P2 - 重要（代码/配置问题）</Select.Option>
              <Select.Option value="P3">P3 - 一般</Select.Option>
            </Select>
          </Form.Item>
          <Form.Item
            name="root_cause"
            label="根因结论"
          >
            <TextArea rows={2} />
          </Form.Item>
          <Form.Item
            name="ai_analysis"
            label="AI分析报告"
          >
            <TextArea rows={8} style={{ fontFamily: 'monospace', fontSize: 12 }} />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}

'use client';

import React, { useState } from 'react';
import { useRouter } from 'next/navigation';
import { startIncomeVerification } from '../lib/api';
import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/Card';
import { Button } from '../components/ui/Button';

export default function DashboardPage() {
  const [appId, setAppId] = useState('SYN-SHB-2026-0001');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const router = useRouter();

  const handleStartWorkflow = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      const res = await startIncomeVerification(appId);
      router.push(`/cases/${res.case_id}`);
    } catch (err: any) {
      setError(err.message || 'Lỗi hệ thống');
      setLoading(false);
    }
  };

  return (
    <div className="max-w-2xl mx-auto mt-10">
      <Card>
        <CardHeader>
          <CardTitle className="text-2xl text-slate-800">Khởi tạo Thẩm định Thu nhập</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-slate-500 mb-6">
            Nhập mã hồ sơ (Application ID) để kích hoạt luồng AI tự động bóc tách và phân tích thu nhập của khách hàng.
          </p>

          <form onSubmit={handleStartWorkflow} className="space-y-4">
            <div className="space-y-2">
              <label className="text-sm font-medium text-slate-700">Application ID</label>
              <input
                type="text"
                value={appId}
                onChange={e => setAppId(e.target.value)}
                className="w-full p-3 border rounded-md focus:ring-2 focus:ring-blue-500 outline-none"
                placeholder="VD: SYN-SHB-2026-0001"
                required
              />
            </div>

            {error && (
              <div className="p-3 bg-red-50 text-red-600 rounded-md text-sm border border-red-200">
                {error}
              </div>
            )}

            <Button type="submit" size="lg" className="w-full" disabled={loading || !appId}>
              {loading ? 'Đang khởi tạo...' : 'Bắt đầu Thẩm định (Start Workflow)'}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}

export default function App() {
  return <div className="layout"><aside className="aside"><div className="brand">EduSphere <small>Platform Console · UI shell</small></div><nav><div className="selected">Architecture Preview</div><div>Tenants (planned)</div><div>Billing (planned)</div><div>Platform operations (planned)</div></nav></aside>
    <main><div className="eyebrow">Sprint 0 v2 · planned / not implemented</div><h1>Platform Console</h1>
      <p>Giao diện định hướng. Backend Sprint 0 chưa có Platform Super Admin API, tenant provisioning, billing hay monitoring.</p>
      <section className="card"><h2>Product boundary</h2><p>Không cung cấp chức năng quản trị tenant và không cho phép truy cập dữ liệu trường. Sprint 1 mới bổ sung API, quyền và audit.</p>
      <button disabled title="Chưa triển khai">Create Tenant · Coming Later</button></section>
    </main></div>
}

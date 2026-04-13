export default function Footer() {
  return (
    <footer className="border-t border-border py-12 bg-bg-base">
      <div className="max-w-[1200px] mx-auto px-6">
        <div className="flex flex-col md:flex-row items-center justify-between gap-6">
          <div className="flex items-center gap-2">
            <span className="w-6 h-6 rounded-md bg-accent flex items-center justify-center text-[#080808] font-bold text-xs">S</span>
            <span className="text-text-1 font-semibold text-sm">SecureMask</span>
          </div>
          <div className="flex items-center gap-6 text-text-3 text-xs">
            <a href="#" className="hover:text-text-2 transition-colors">privacy</a>
            <a href="#" className="hover:text-text-2 transition-colors">terms</a>
            <a href="#" className="hover:text-text-2 transition-colors">docs</a>
            <a href="#" className="hover:text-text-2 transition-colors">github</a>
          </div>
          <p className="text-text-3 text-xs">© 2026 SecureMask. built for india's dpdp act.</p>
        </div>
      </div>
    </footer>
  )
}

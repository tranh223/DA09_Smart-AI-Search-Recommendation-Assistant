import { useState } from 'react';
import { NavBar } from '../components/layout/NavBar';
import { HeroSection } from '../components/sections/HeroSection';
import { SearchSection } from '../components/search/SearchSection';
import { DestinationsSection } from '../components/product_card/DestinationsSection';
import { FeaturesStrip } from '../components/sections/FeaturesStrip';
import { TestimonialsSection } from '../components/sections/TestimonialsSection';
import { Footer } from '../components/layout/Footer';
import { ChatBot } from '../components/chat/ChatBot';

export function HomePage() {
  const [chatOpen, setChatOpen] = useState(false);

  return (
    <div style={{
      fontFamily: "'Be Vietnam Pro', sans-serif",
      background: '#FFFDF8',
      color: '#2A1A1A',
      overflowX: 'hidden',
      minHeight: '100vh',
    }}>
      <NavBar />
      <HeroSection onOpenChat={() => setChatOpen(true)} />
      <SearchSection />
      <DestinationsSection />
      <FeaturesStrip />
      <TestimonialsSection />
      <Footer />
      <ChatBot
        isOpen={chatOpen}
        onOpen={() => setChatOpen(true)}
        onClose={() => setChatOpen(false)}
      />
    </div>
  );
}

import { t } from '../styles/theme';
import { NavBar, type Route } from '../components/layout/NavBar';
import { HeroSection } from '../components/sections/HeroSection';
import { SearchSection } from '../components/search/SearchSection';
import { DestinationsSection } from '../components/product_card/DestinationsSection';
import { FeaturesStrip } from '../components/sections/FeaturesStrip';
import { TestimonialsSection } from '../components/sections/TestimonialsSection';
import { Footer } from '../components/layout/Footer';
import { CHAT_DOCK_WIDTH } from '../components/chat/ChatBot';
import { type HotelListParams } from '../services/hotels';

export function HomePage({
  onNavigate,
  onOpenChat,
  onSearchHotels,
  chatOpen = false,
}: {
  onNavigate?: (route: Route) => void;
  onOpenChat?: () => void;
  onSearchHotels?: (params: HotelListParams) => void;
  chatOpen?: boolean;
}) {
  return (
    <div style={{
      fontFamily: t.font,
      background: t.bg,
      color: t.ink,
      overflowX: 'hidden',
      minHeight: '100vh',
      paddingRight: chatOpen ? CHAT_DOCK_WIDTH : 0,
      transition: 'padding-right .3s ease',
    }}>
      <NavBar active="home" onNavigate={onNavigate} />
      <HeroSection onOpenChat={() => onOpenChat?.()} />
      <SearchSection
        onSearch={({ destination, starRatingMin }) => {
          onSearchHotels?.({
            ...(destination ? { city: destination } : {}),
            ...(starRatingMin != null ? { star_rating_min: starRatingMin } : {}),
          });
        }}
      />
      <DestinationsSection onSeeAll={() => onNavigate?.('hotels')} />
      <FeaturesStrip />
      <TestimonialsSection />
      <Footer />
    </div>
  );
}

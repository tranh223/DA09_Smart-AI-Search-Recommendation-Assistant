import { ImageWithFallback } from '../common/ImageWithFallback';

const DESTINATIONS = [
  {
    name: 'Phú Quốc',
    rating: '★★★★★',
    reviews: '4.9 (1.2k đánh giá)',
    price: 'từ 2.9tr₫',
    badge: 'Hot ✦',
    rotate: '-0.5deg',
    image: 'https://images.unsplash.com/photo-1732243395944-cb3ff9311091?w=480&h=310&fit=crop&auto=format',
    imageAlt: 'Bãi biển Phú Quốc với cát trắng và cọ xanh',
  },
  {
    name: 'Đà Nẵng',
    rating: '★★★★★',
    reviews: '4.8 (980 đánh giá)',
    price: 'từ 1.8tr₫',
    rotate: '0.7deg',
    image: 'https://images.unsplash.com/photo-1573270689103-d7a4e42b609a?w=480&h=310&fit=crop&auto=format',
    imageAlt: 'Thành phố Đà Nẵng và vịnh biển',
  },
  {
    name: 'Hội An',
    rating: '★★★★★',
    reviews: '4.9 (2.1k đánh giá)',
    price: 'từ 1.5tr₫',
    badge: 'Mới ✦',
    rotate: '-0.5deg',
    image: 'https://images.unsplash.com/photo-1596401057633-54a8fe8ef647?w=480&h=310&fit=crop&auto=format',
    imageAlt: 'Đèn lồng lung linh phố cổ Hội An',
  },
  {
    name: 'Hạ Long',
    rating: '★★★★★',
    reviews: '5.0 (3.4k đánh giá)',
    price: 'từ 3.2tr₫',
    rotate: '0.7deg',
    image: 'https://images.unsplash.com/photo-1431975071466-2c609dac5956?w=480&h=310&fit=crop&auto=format',
    imageAlt: 'Vịnh Hạ Long với những hòn đảo đá vôi',
  },
];

export function DestinationsSection() {
  return (
    <section style={{ padding: '60px 40px 30px' }}>
      <div style={{ display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between', marginBottom: '28px' }}>
        <h2 style={{ fontFamily: "'Baloo 2', sans-serif", fontSize: '38px', fontWeight: 700, color: '#2A1A1A', lineHeight: 1.1, margin: 0 }}>
          Điểm đến <span style={{ color: '#D42B2B' }}>nổi bật</span> 🌟
        </h2>
        <a href="#" style={{
          fontFamily: "'Pangolin', cursive", fontSize: '16px', color: '#D42B2B',
          textDecoration: 'none', borderBottom: '1.5px dashed #D42B2B', paddingBottom: '2px',
        }}>
          Xem tất cả →
        </a>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '20px' }}>
        {DESTINATIONS.map((d, i) => (
          <DestCard key={i} {...d} />
        ))}
      </div>
    </section>
  );
}

interface DestCardProps {
  name: string;
  rating: string;
  reviews: string;
  price: string;
  badge?: string;
  rotate: string;
  image: string;
  imageAlt: string;
}

function DestCard({ name, rating, reviews, price, badge, rotate, image, imageAlt }: DestCardProps) {
  return (
    <div
      style={{
        border: '2px solid #F5DADA',
        borderRadius: '18px',
        overflow: 'hidden',
        background: 'white',
        cursor: 'pointer',
        boxShadow: '3px 3px 0 #F5DADA',
        position: 'relative',
        transform: `rotate(${rotate})`,
        transition: 'transform .2s, box-shadow .2s',
      }}
      onMouseEnter={e => {
        (e.currentTarget as HTMLDivElement).style.transform = 'rotate(0deg) translateY(-6px)';
        (e.currentTarget as HTMLDivElement).style.boxShadow = '6px 8px 0 #F5DADA';
        (e.currentTarget as HTMLDivElement).style.borderColor = '#D42B2B';
      }}
      onMouseLeave={e => {
        (e.currentTarget as HTMLDivElement).style.transform = `rotate(${rotate})`;
        (e.currentTarget as HTMLDivElement).style.boxShadow = '3px 3px 0 #F5DADA';
        (e.currentTarget as HTMLDivElement).style.borderColor = '#F5DADA';
      }}
    >
      <div style={{ width: '100%', height: '155px', overflow: 'hidden', position: 'relative', background: '#FDE8E0' }}>
        <ImageWithFallback
          src={image}
          alt={imageAlt}
          style={{ width: '100%', height: '100%', objectFit: 'cover', display: 'block' }}
        />
        {badge && (
          <div style={{
            position: 'absolute', top: '10px', left: '10px',
            background: '#D42B2B', color: 'white',
            fontFamily: "'Pangolin', cursive", fontSize: '13px',
            padding: '3px 10px', borderRadius: '99px',
            border: '1.5px solid #A01E1E', transform: 'rotate(-3deg)',
          }}>
            {badge}
          </div>
        )}
      </div>
      <div style={{ padding: '12px 14px' }}>
        <div style={{ fontFamily: "'Baloo 2', sans-serif", fontSize: '21px', fontWeight: 700, color: '#2A1A1A', marginBottom: '4px' }}>
          {name}
        </div>
        <div style={{ fontSize: '13px', color: '#5A3A3A', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div>
            <div style={{ color: '#D42B2B', fontSize: '12px' }}>{rating}</div>
            <span style={{ fontSize: '12px', color: '#888' }}>{reviews}</span>
          </div>
          <div style={{ fontFamily: "'Baloo 2', sans-serif", fontSize: '17px', fontWeight: 700, color: '#D42B2B' }}>{price}</div>
        </div>
      </div>
    </div>
  );
}

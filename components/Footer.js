// components/Footer.js
import React from 'react';
import { FaFacebook, FaTwitter, FaInstagram, FaLinkedin, FaYoutube, FaLink } from 'react-icons/fa';

// Map social labels to icon components
const iconMap = {
  Facebook: FaFacebook,
  Twitter: FaTwitter,
  Instagram: FaInstagram,
  LinkedIn: FaLinkedin,
  YouTube: FaYoutube,
};

export default function Footer() {
  // Parse NEXT_PUBLIC_SOCIALS: e.g. "Facebook|https://...,..."
  const socialsEnv = process.env.NEXT_PUBLIC_SOCIALS || '';
  const socials = socialsEnv.split(',').reduce((arr, item) => {
    const [label, url] = item.split('|');
    if (label && url) {
      arr.push({ 
        label: label.trim(), 
        url: url.trim() 
      });
    }
    return arr;
  }, []);

  return (
    <footer className="footer">
      <div className="social-links">
        {socials.map(({ label, url }) => {
          const IconComponent = iconMap[label] || FaLink;
          return (
            <a 
              key={label} 
              href={url} 
              target="_blank" 
              rel="noopener noreferrer"
              className="social-link"
            >
              <IconComponent /> {label}
            </a>
          );
        })}
      </div>
    </footer>
  );
}

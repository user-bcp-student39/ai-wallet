import { Routes } from '@angular/router';
import { RegistrationPage } from './pages/registration-page';
import { VerificationPage } from './pages/verification-page';
import { WalletPage } from './pages/wallet-page';

export const routes: Routes = [
  { path: '', redirectTo: 'registro', pathMatch: 'full' },
  { path: 'registro', component: RegistrationPage },
  { path: 'verificacion/:id', component: VerificationPage },
  { path: 'wallet/:id', component: WalletPage },
  { path: '**', redirectTo: 'registro' },
];
